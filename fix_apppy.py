#!/usr/bin/env python3
"""
Mint Scan — App.py Fixer
Run this on your Chromebook to fix all tab errors.
"""
import os, sys

target = os.path.expanduser('~/mint-scan-linux/app.py')
if not os.path.exists(target):
    print(f"ERROR: {target} not found")
    sys.exit(1)

with open(target) as f:
    content = f.read()

OLD_IMPORTS = """        # Import screens here to avoid circular imports
        from dash     import DashScreen
        from perms    import PermsScreen
        from wifi     import WifiScreen
        from calls    import CallsScreen
        from network  import NetworkScreen
        from battery  import BatteryScreen
        from threats  import ThreatsScreen
        from notifs   import NotifsScreen
        from ports    import PortsScreen"""

NEW_IMPORTS = """        # Import screens — with safe fallback for missing screens
        import importlib, sys as _sys
        _base = os.path.dirname(os.path.abspath(__file__))
        if _base not in _sys.path: _sys.path.insert(0, _base)

        from dash     import DashScreen
        from perms    import PermsScreen
        from wifi     import WifiScreen
        from calls    import CallsScreen
        from network  import NetworkScreen
        from battery  import BatteryScreen
        from threats  import ThreatsScreen
        from notifs   import NotifsScreen
        from ports    import PortsScreen

        def _safe_import(mod, cls):
            try:
                m = importlib.import_module(mod)
                return getattr(m, cls)
            except Exception as e:
                print(f"  Note: {mod} not available ({e}) — tab hidden")
                return None

        UsbScreen     = _safe_import('usb',     'UsbScreen')
        NetScanScreen = _safe_import('netscan', 'NetScanScreen')
        MalwareScreen = _safe_import('malware', 'MalwareScreen')
        SysFixScreen  = _safe_import('sysfix',  'SysFixScreen')"""

OLD_TABS = """        TABS = [
            ('⬡ DASHBOARD',  'dash'),
            ('🔑 PERMISSIONS','perms'),
            ('📶 WI-FI',      'wifi'),
            ('📞 CALLS',      'calls'),
            ('📡 NETWORK',    'network'),
            ('🔋 BATTERY',    'battery'),
            ('⚠  THREATS',    'threats'),
            ('🔔 NOTIFS',     'notifs'),
            ('🔍 PORT SCAN',  'ports'),
            ('📱 USB SYNC',   'usb'),
            ('🔬 NET SCAN',   'netscan'),
            ('🦠 MALWARE',    'malware'),
            ('🔧 SYS FIX',    'sysfix'),
        ]"""

NEW_TABS = """        _ALL_TABS = [
            ('⬡ DASHBOARD',  'dash',    DashScreen),
            ('🔑 PERMISSIONS','perms',   PermsScreen),
            ('📶 WI-FI',      'wifi',    WifiScreen),
            ('📞 CALLS',      'calls',   CallsScreen),
            ('📡 NETWORK',    'network', NetworkScreen),
            ('🔋 BATTERY',    'battery', BatteryScreen),
            ('⚠  THREATS',    'threats', ThreatsScreen),
            ('🔔 NOTIFS',     'notifs',  NotifsScreen),
            ('🔍 PORT SCAN',  'ports',   PortsScreen),
            ('📱 USB SYNC',   'usb',     UsbScreen),
            ('🔬 NET SCAN',   'netscan', NetScanScreen),
            ('🦠 MALWARE',    'malware', MalwareScreen),
            ('🔧 SYS FIX',    'sysfix',  SysFixScreen),
        ]
        TABS = [(lbl, key) for lbl, key, cls in _ALL_TABS if cls is not None]
        screen_classes_full = {key: cls for _, key, cls in _ALL_TABS if cls is not None}"""

OLD_CLASSES = """        screen_classes = {
            'dash':    DashScreen,
            'perms':   PermsScreen,
            'wifi':    WifiScreen,
            'calls':   CallsScreen,
            'network': NetworkScreen,
            'battery': BatteryScreen,
            'threats': ThreatsScreen,
            'notifs':  NotifsScreen,
            'ports':   PortsScreen,
            'usb':     UsbScreen,
            'netscan': NetScanScreen,
            'malware': MalwareScreen,
            'sysfix':  SysFixScreen,
        }"""

NEW_CLASSES = "        screen_classes = screen_classes_full"

changed = False
for old, new in [(OLD_IMPORTS, NEW_IMPORTS), (OLD_TABS, NEW_TABS), (OLD_CLASSES, NEW_CLASSES)]:
    if old in content:
        content = content.replace(old, new)
        changed = True
        print(f"  ✓ Patched block")
    else:
        print(f"  (block already patched or different)")

if changed:
    with open(target, 'w') as f:
        f.write(content)
    print(f"\n✓ app.py fixed at {target}")
else:
    print("\napp.py already up to date or has different structure")

print("\nNow run:")
print("  source venv/bin/activate && python3 main.py")
