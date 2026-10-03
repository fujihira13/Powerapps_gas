"""Keep the management panels while providing a supported scroll focus target."""
from pathlib import Path
import shutil
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'outputs/environment-management-20261003/server-navigation'

def find(node, name):
    if isinstance(node, dict):
        if name in node:
            return node[name]
        for value in node.values():
            found = find(value, name)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = find(value, name)
            if found is not None:
                return found
    return None

def add_scroll_focus(app):
    """Apply the accepted display change to a newly generated Screen5."""
    screen = app['Screens']['Screen5']
    scroll = find(screen, 'conM05Scroll')
    center = find(scroll, 'conM05Center')
    server = find(center, 'srvM05Panel')
    context = find(server, 'lblM05EnvContext')
    server['Children'] = [child for child in server['Children'] if 'lblM05EnvContext' not in child]
    scroll['Control'] = 'FluidGrid'
    scroll.pop('Variant', None)
    scroll['Properties'] = {
        'BorderThickness': '=0', 'Height': '=Parent.Height', 'Width': '=Parent.Width',
        'X': '=0', 'Y': '=0',
    }
    props = center['Properties']
    for key in ('AlignInContainer', 'FillPortions', 'LayoutMinHeight', 'LayoutMinWidth'):
        props.pop(key, None)
    props['Height'] = '=Max(Screen5.Height, pnlM05Lists.Y + pnlM05Lists.Height + 24)'
    props['X'] = '=(Parent.Width - Self.Width) / 2'
    props['Y'] = '=0'
    cp = context['Properties']
    cp['Text'] = '="対象の環境：" & Coalesce(varM05Env, "")'
    cp['TabIndex'] = '=0'
    cp['Role'] = '=TextRole.Heading2'
    cp['Width'] = '=srvM05Panel.Width - 36'
    cp['X'] = '=conM05Center.X + pnlM05Lists.X + srvM05Panel.X + 18'
    cp['Y'] = '=conM05Center.Y + pnlM05Lists.Y + srvM05Panel.Y + 72'
    scroll['Children'] = [{
        'crdM05ScrollBody': {
            'Control': 'DataCard', 'Variant': 'BlankCard',
            'Properties': {'Height': '=conM05Center.Height', 'Width': '=Parent.Width', 'X': '=0', 'Y': '=0'},
            'Children': [{'conM05Center': center}, {'lblM05EnvContext': context}],
        }
    }]
    # The new control type has a different authoring identity.
    screen['Children'][0] = {'grdM05Scroll': scroll}
    button = find(center, 'btnM05ViewServers')
    button['Properties']['OnSelect'] += '; SetFocus(lblM05EnvContext)'
    return app

class MultilineDumper(yaml.SafeDumper):
    pass
def represent_string(dumper, value):
    return dumper.represent_scalar('tag:yaml.org,2002:str', value, style='|' if '\n' in value else None)
MultilineDumper.add_representer(str, represent_string)
def main():
    baseline = WORK / 'baseline'
    candidate = WORK / 'candidate'
    candidate.mkdir(parents=True, exist_ok=True)
    for source in baseline.glob('*.pa.yaml'):
        shutil.copy2(source, candidate / source.name)
    path = candidate / 'Screen5.pa.yaml'
    app = add_scroll_focus(yaml.safe_load(path.read_text(encoding='utf-8-sig')))
    path.write_text(yaml.dump(app, Dumper=MultilineDumper, allow_unicode=True, sort_keys=False, width=10000), encoding='utf-8')
    assert yaml.safe_load(path.read_text(encoding='utf-8')) == app
    print('Prepared Screen5 scroll focus; all other definitions copied unchanged.')

if __name__ == '__main__':
    main()
