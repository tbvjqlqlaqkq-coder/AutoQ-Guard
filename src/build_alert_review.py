"""Build a read-only public grouped view; preserve all fixed-rule alarm rows."""
import csv
import hashlib
import html
import json
from datetime import date
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = ('BRAND', 'MODEL', 'YEAR', 'CAT')
if __package__:
    from .repeated_alert_audit import audit
else:
    from repeated_alert_audit import audit


def render(rows):
    if not rows:
        raise ValueError('No evaluation rows')
    groups = defaultdict(list)
    seen = set()
    for row in rows:
        key = tuple(row[k] for k in KEY)
        if any(not str(v).strip() for v in key):
            raise ValueError('Empty group key')
        dt = date.fromisoformat(row['MONTH'])
        if dt.day != 1:
            raise ValueError('Expected month start')
        if (key, row['MONTH']) in seen:
            raise ValueError('Duplicate group-month')
        seen.add((key, row['MONTH']))
        if row['fixed_rule'] not in ('0', '1') or row['Y12'] not in ('0', '1'):
            raise ValueError('Invalid binary value')
        if row['fixed_rule'] == '1':
            groups[key].append(row)
    esc = html.escape
    cards = []
    for key, alarms in sorted(groups.items()):
        body = ''
        for i, r in enumerate(sorted(alarms, key=lambda r: r['MONTH'])):
            body += f'<tr data-alert-row><td>{esc(r["MONTH"][:7])}</td><td>{"期間内初回" if i == 0 else "추가 경보 · 원본 유지"}</td><td>{"양성" if r["Y12"] == "1" else "음성"}</td></tr>'
        title = esc(' / '.join(key))
        cards.append(f'<details class="group"><summary>{title} <b>{len(alarms)}건</b></summary><p>신규 결함·심각도 변화 여부: 판단 불가 — 원본 안전 신호와 처리 이력 연결 필요</p><table><thead><tr><th>경보 월</th><th>표시 상태</th><th>사후 Y12 라벨</th></tr></thead><tbody>{body}</tbody></table></details>')
    count = sum(map(len, groups.values()))
    comparisons = [audit(rows, 'fixed_rule', p) for p in ('monthly', 'consecutive', 'cooldown_3m')]
    if any(r['raw_alert_rows'] != count for r in comparisons):
        raise ValueError('Audit and display counts differ')
    chart = '<section class="chart"><h2>계산 결과: 검토를 생략하면 어떻게 되나?</h2>'
    for label, result in zip(('모두 검토', '연속 경보 첫 회만', '3개월 간격'), comparisons):
        width = 100 * result['review_rows'] / count if count else 0
        chart += (f'<div>{label} · {result["review_rows"]}건 ({result["reduction_rate"]:.1%} 감소)</div>'
                  f'<div class="bar" style="width:{width:.2f}%"></div>'
                  f'<p>양성 행을 유지하지 못한 연속 구간: {result["positive_episodes_without_retained_positive"]}/{result["positive_episodes"]}</p>')
    chart += '<p>이 숫자는 실제 리콜 사건 수가 아니며 안전성을 보증하지 않습니다. 아래 목록에는 억제 방식을 적용하지 않았습니다. 양성 구간이 0이면 평가할 양성 사례가 없다는 뜻입니다.</p><a href="../model_validation/REPEATED_ALERT_AUDIT.md">기존 검증 보고서 (별도 실행 시점)</a></section>'
    period = min(r['MONTH'] for r in rows)[:7] + ' ~ ' + max(r['MONTH'] for r in rows)[:7]
    output = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AutoQ-Guard | 반복 경보 검토</title><style>
*{box-sizing:border-box}body{margin:0;background:#edf2f7;color:#102033;font:16px/1.7 'Malgun Gothic',sans-serif}header{background:#10243b;color:white;padding:32px max(24px,calc((100% - 1100px)/2))}header a{color:#70d8ea}main{max-width:1150px;margin:auto;padding:24px}h1{margin:12px 0}h2{font-size:20px}.note{background:#fff3eb;border-left:5px solid #ff6a3d;padding:16px}.stats{display:flex;gap:14px;flex-wrap:wrap;margin:20px 0}.stats article{background:white;padding:18px;flex:1;min-width:160px;border-radius:12px}.stats strong{display:block;font-size:30px;color:#176a89}.group{background:white;border:1px solid #dbe3ec;border-radius:10px;margin:10px 0;padding:14px}summary{cursor:pointer;font-weight:bold}summary b{color:#176a89;margin-left:12px}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px;border-bottom:1px solid #e5ebf1}input,button{font:inherit;padding:10px;border:1px solid #bac9d7;border-radius:7px}input{width:min(100%,440px)}button{background:#10243b;color:white;cursor:pointer}.controls{display:flex;gap:10px;flex-wrap:wrap}p{overflow-wrap:anywhere}.chart{background:white;padding:18px;border-radius:12px;margin:20px 0}.bar{height:16px;background:#21b8d4;margin:4px 0 12px}.bar.base{background:#ff6a3d}[hidden]{display:none!important}small{color:#586a7b}
</style><header><a href="index.html">← 공개 데모로 돌아가기</a><h1>경보는 보존하고, 검토 화면만 묶습니다</h1><p>공개자료 기반 · 2025년 1~6월 성숙한 테스트 구간 · 고정 규칙</p></header><main>
<p class="note">사후 검증 화면입니다. 실시간 기업 경보가 아니며, Y12는 나중에 확인된 평가용 라벨입니다. 검색·묶음은 경보를 삭제하거나 검토 완료로 처리하지 않습니다.</p>
''' + f'<section class="stats"><article>원본 경보<strong>{count}건</strong></article><article>펼쳐볼 차량 그룹<strong>{len(groups)}개</strong></article><article>삭제·자동 억제<strong>0건</strong></article></section>' + '''
''' + chart + '''
<h2>차량 그룹별 원본 경보</h2><p>LOT·VIN이 아닌 제조사 / 차종 / 연식 / 부품분류로 묶습니다. 같은 그룹이라도 동일 결함이라는 뜻은 아닙니다. ‘추가 경보’는 기간 내 두 번째 이후 기록을 뜻하며 실제 신규 사건 판정이 아닙니다.</p>
<div class="controls"><label>그룹 검색 <input id="filter" type="search" placeholder="예: HYUNDAI, ABS, 2015"></label><button id="expand">검색 결과 펼치기</button><button id="collapse">접기</button></div><p id="status" role="status" aria-live="polite"></p><div id="groups">''' + ''.join(cards).replace('期間内初回', '기간 내 첫 경보') + '''</div>
<p><small>표시 한계: 신규 안전사고, 심각도 상승, 조사 개시 및 담당자 검토 이력은 연결되지 않았습니다. 기업 적용 전 사건 연결·재알림 규칙을 별도로 검증해야 합니다. 비용 절감률이나 리콜 예방 대수는 입증하지 않습니다.</small></p></main>
<script>
const groups=[...document.querySelectorAll('.group')], input=document.getElementById('filter');
function filter(){const q=input.value.trim().toLowerCase();let n=0;groups.forEach(g=>{g.hidden=!g.querySelector('summary').textContent.toLowerCase().includes(q);if(!g.hidden)n++});document.getElementById('status').textContent=n?`${n}개 그룹 표시 · 제목을 누르면 원본 경보가 나옵니다.`:'검색 결과가 없습니다. 검색어를 바꿔 주세요.'}
input.addEventListener('input',filter);document.getElementById('expand').onclick=()=>groups.filter(g=>!g.hidden).forEach(g=>g.open=true);document.getElementById('collapse').onclick=()=>groups.forEach(g=>g.open=false);filter();
</script></html>'''
    if output.count('<tr data-alert-row>') != count or output.count('<details class="group">') != len(groups):
        raise ValueError('Rendered rows or groups differ from input')
    return output.replace('2025년 1~6월 성숙한 테스트 구간', esc(period) + ' 입력 평가 구간')


def main():
    source = ROOT/'results/purged_ml/test_predictions.csv'
    with source.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    output = render(rows)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    output += '\n<!-- source sha256: ' + digest + ' -->\n'
    (ROOT/'docs/demo/alert-review.html').write_text(output, encoding='utf-8')
    receipt = dict(source_sha256=digest, html_sha256=hashlib.sha256(output.encode('utf-8')).hexdigest(),
                   input_rows=len(rows), original_alerts=sum(r['fixed_rule']=='1' for r in rows),
                   rendered_alerts=output.count('<tr data-alert-row>'),
                   rendered_groups=output.count('<details class="group">'),
                   comparisons=[audit(rows,'fixed_rule',p) for p in ('monthly','consecutive','cooldown_3m')],
                   validation_scope='Build consistency only; not enterprise effectiveness or browser interaction validation')
    (ROOT/'docs/model_validation/alert_review_build.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print('Built docs/demo/alert-review.html')


if __name__ == '__main__':
    main()
