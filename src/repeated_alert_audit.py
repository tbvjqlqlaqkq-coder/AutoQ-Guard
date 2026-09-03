"""Retrospective workload experiment; never changes live alert handling."""
import csv
import hashlib
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = ('BRAND', 'MODEL', 'YEAR', 'CAT')
MODELS = ('fixed_rule', 'logistic_regression', 'random_forest')


def audit(rows, model, policy):
    if policy not in ('monthly', 'consecutive', 'cooldown_3m'):
        raise ValueError('Unknown policy')
    groups = defaultdict(list)
    seen = set()
    for row in rows:
        key = tuple(row[k] for k in KEY)
        dt = date.fromisoformat(row['MONTH'])
        if dt.day != 1:
            raise ValueError('Expected month start')
        month = dt.year * 12 + dt.month
        if (key, month) in seen:
            raise ValueError('Duplicate group-month')
        seen.add((key, month))
        if row[model] not in ('0', '1') or row['Y12'] not in ('0', '1'):
            raise ValueError('Binary strings required')
        groups[key].append((month, int(row[model]), int(row['Y12'])))
    alerts = kept = positives = kept_positive = episodes = positive_episodes = uncovered = 0
    monthly = defaultdict(lambda: dict(raw=0, kept=0))
    for observations in groups.values():
        last_alert = last_kept = None
        episode = []
        all_episodes = []
        for month, alarm, label in sorted(observations):
            if not alarm:
                continue
            consecutive = last_alert is not None and month == last_alert + 1
            if not consecutive and episode:
                all_episodes.append(episode)
                episode = []
            # Decisions use only past alert times, never future outcomes.
            retain = (policy == 'monthly' or
                      policy == 'consecutive' and not consecutive or
                      policy == 'cooldown_3m' and (last_kept is None or month-last_kept >= 3))
            alerts += 1
            kept += int(retain)
            positives += label
            kept_positive += label * int(retain)
            monthly[month]['raw'] += 1
            monthly[month]['kept'] += int(retain)
            episode.append((label, retain))
            last_alert = month
            if retain:
                last_kept = month
        if episode:
            all_episodes.append(episode)
        for episode in all_episodes:
            episodes += 1
            if any(label for label, _ in episode):
                positive_episodes += 1
                uncovered += int(not any(label and retain for label, retain in episode))
    return dict(model=model, policy=policy, raw_alert_rows=alerts, review_rows=kept,
                suppressed_rows=alerts-kept, reduction_rate=(alerts-kept)/alerts if alerts else 0,
                positive_alert_rows=positives, retained_positive_rows=kept_positive,
                suppressed_positive_rows=positives-kept_positive, consecutive_episodes=episodes,
                positive_episodes=positive_episodes, positive_episodes_without_retained_positive=uncovered,
                monthly={str(k): v for k, v in sorted(monthly.items())})


def main():
    source = ROOT/'results/purged_ml/test_predictions.csv'
    with source.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    results = [audit(rows, m, p) for m in MODELS for p in ('monthly', 'consecutive', 'cooldown_3m')]
    out = ROOT/'docs/model_validation'
    payload = dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                   period='2025-01 through 2025-06, mature test rows only',
                   retrospective=True, production_policy_changed=False, results=results)
    (out/'repeated_alert_results.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
    lines = ['# 반복 경보 묶음 검증', '',
      '기존 예측값을 고정한 사후 탐색입니다. 운영 경보는 변경하지 않았습니다.', '',
      '## 사전에 정한 비교 방식', '',
      '- 매월 검토: 모든 경보를 유지합니다.',
      '- 연속 묶음: 같은 제조사·차종·연식·부품분류에서 연속으로 경보가 난 기간의 첫 경보만 유지합니다. 한 달 이상 경보가 없으면 다시 검토합니다.',
      '- 3개월 간격: 검토한 월 이후 2개월은 묶고 3개월째 다시 검토합니다.',
      '- 결정에는 과거 경보 시점만 사용합니다. Y12는 결과 평가에만 사용합니다.', '',
      '| 모델 | 방식 | 원래 경보 | 검토 유지 | 감소율 | 묶인 양성 행 | 양성 경보를 유지하지 못한 양성 묶음 |',
      '|---|---|---:|---:|---:|---:|---:|']
    for r in results:
        lines.append(f"| {r['model']} | {r['policy']} | {r['raw_alert_rows']} | {r['review_rows']} | {r['reduction_rate']:.1%} | {r['suppressed_positive_rows']} | {r['positive_episodes_without_retained_positive']}/{r['positive_episodes']} |")
    lines += ['', '## 해석과 한계', '',
      '양성 행은 해당 그룹·월의 향후 12개월 리콜 연관 라벨입니다. 실제 결함·리콜 캠페인·예방 차량 수가 아닙니다. 같은 그룹에서도 별개의 결함이 생길 수 있으므로 연속 묶음 역시 동일 사건을 뜻하지 않습니다.', '',
      '양성 경보를 유지하지 못한 양성 묶음은, 원래 양성 경보가 있었지만 묶은 후 그 양성 행이 하나도 유지되지 않은 연속 구간입니다. 최초 음성 경보를 검토했더라도 나중에 발생한 별도 신호를 놓칠 가능성이 있습니다. 이 값은 실제 리콜 미탐 수나 안전성 보증이 아닙니다.', '',
      '2025년 1~6월의 성숙한 테스트 행만 사용하고 1월에는 이전 검토 기록이 없는 것으로 시작했습니다. 관측 누락은 연속성을 끊습니다. 이전 기간의 열린 사건, 실제 검토 완료 상태, 검토 인력 한도, 신규 심각사고·조사 신호는 반영하지 못했습니다.', '',
      '이미 여러 번 확인한 테스트 기간을 이용한 탐색이므로 이 결과로 정책을 선택해도 독립 검증을 마친 것이 아닙니다. 금액 절감이나 ROI로 변환하지 않았습니다.', '',
      '## 적용 판단', '',
      '자동 경보 삭제·억제에는 적용하지 않습니다. 우선 원래 경보를 보존한 채 화면에서 동일 그룹을 묶고 새 경보·심각도 변화·재검토 필요 여부를 드러내는 방식이 적절합니다. 실제 검토량 절감은 사건 식별과 처리 이력, 신규 안전 신호 재알림 규칙을 연결한 뒤 별도 기간에서 검증해야 합니다.', '']
    (out/'REPEATED_ALERT_AUDIT.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
