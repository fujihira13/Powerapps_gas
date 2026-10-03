"""Apply the approved context copy and center the intake chevron."""
from pathlib import Path
import shutil
import yaml
from prepare_server_list_navigation import find, MultilineDumper

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'outputs/environment-management-20261003/context-chevron'

def main():
    candidate = WORK / 'candidate'
    candidate.mkdir(parents=True, exist_ok=True)
    for source in (WORK / 'baseline').glob('*.pa.yaml'):
        shutil.copy2(source, candidate / source.name)
    path = candidate / 'Screen5.pa.yaml'
    app = yaml.safe_load(path.read_text(encoding='utf-8-sig'))
    find(app, 'lblM05EnvContext')['Properties']['Text'] = '="対象の環境：" & Coalesce(varM05Env, "")'
    path.write_text(yaml.dump(app, Dumper=MultilineDumper, allow_unicode=True, sort_keys=False, width=10000), encoding='utf-8')
    path = candidate / 'Screen1.pa.yaml'
    app = yaml.safe_load(path.read_text(encoding='utf-8-sig'))
    card = find(app, '環境名_DataCard1')
    find(card, 'envS01Arrow')['Properties']['Text'] = '=""'
    index = next(i for i, child in enumerate(card['Children']) if 'envS01Arrow' in child)
    card['Children'].insert(index + 1, {'envS01Chevron': {
        'Control': 'Classic/Icon',
        'Properties': {
            'AccessibleLabel': '="環境の候補を開閉する"',
            'Color': '=RGBA(255, 255, 255, 1)',
            'DisplayMode': '=envS01ValueBridge.DisplayMode',
            'Height': '=20', 'Width': '=20',
            'HoverColor': '=RGBA(255, 255, 255, 1)',
            'PressedColor': '=RGBA(255, 255, 255, 1)',
            'Icon': '=Icon.ChevronDown',
            'OnSelect': '=Select(envS01Field)',
            'Tooltip': '="環境の候補を開閉する"',
            'X': '=envS01Arrow.X + (envS01Arrow.Width - Self.Width) / 2',
            'Y': '=envS01Arrow.Y + (envS01Arrow.Height - Self.Height) / 2',
        }
    }})
    path.write_text(yaml.dump(app, Dumper=MultilineDumper, allow_unicode=True, sort_keys=False, width=10000), encoding='utf-8')
    print('Prepared two scoped screen edits from the synced baseline.')

if __name__ == '__main__':
    main()
