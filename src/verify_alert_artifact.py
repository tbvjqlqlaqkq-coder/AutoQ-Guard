"""Verify committed public artifacts without private/raw data or ML packages."""
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Counts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = self.groups = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.rows += int(tag == 'tr' and 'data-alert-row' in attrs)
        self.groups += int(tag == 'details' and 'group' in attrs.get('class', '').split())


def verify(document, receipt):
    # Git may convert CRLF on Windows. The generator hashes logical LF text.
    normalized = document.replace('\r\n', '\n')
    if hashlib.sha256(normalized.encode('utf-8')).hexdigest() != receipt['html_sha256']:
        raise ValueError('HTML differs from build receipt; regenerate before publishing')
    parser = Counts()
    parser.feed(normalized)
    if not (parser.rows == receipt['rendered_alerts'] == receipt['original_alerts']):
        raise ValueError('Alert counts differ')
    if parser.groups != receipt['rendered_groups']:
        raise ValueError('Group counts differ')
    if receipt['input_rows'] < parser.rows:
        raise ValueError('More alarms than input rows')
    if '<!-- source sha256: ' + receipt['source_sha256'] + ' -->' not in normalized:
        raise ValueError('Source fingerprint differs')
    comparisons = receipt['comparisons']
    if [c['policy'] for c in comparisons] != ['monthly', 'consecutive', 'cooldown_3m']:
        raise ValueError('Unexpected comparison policies')
    for c in comparisons:
        if c['raw_alert_rows'] != parser.rows or not 0 <= c['review_rows'] <= parser.rows:
            raise ValueError('Invalid comparison counts')
    return dict(status='PASS', alerts=parser.rows, groups=parser.groups,
                scope='Artifact consistency, not model effectiveness or browser testing')


def main():
    document = (ROOT/'docs/demo/alert-review.html').read_text(encoding='utf-8')
    receipt = json.loads((ROOT/'docs/model_validation/alert_review_build.json').read_text(encoding='utf-8'))
    print(json.dumps(verify(document, receipt)))


if __name__ == '__main__':
    main()
