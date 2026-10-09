from PySide6.QtGui import QColor, QPalette

THEMES = {
    "Midnight": {"bg":"#0b1020","panel":"#11182b","input":"#0c1324","text":"#e7eaf2","muted":"#91a0bd","border":"#283653","accent":"#6d5dfc","accent2":"#8b7fff","selected":"#303b68","selected_text":"#ffffff","hover":"#202d4b","console":"#070b15","button":"#1b2540","danger":"#7f2944","danger_border":"#b83e62","success":"#176044","success_border":"#2d8a66","disabled":"#20283a"},
    "Light": {"bg":"#f5f7fb","panel":"#ffffff","input":"#ffffff","text":"#182033","muted":"#5f6b83","border":"#cbd5e1","accent":"#4f46e5","accent2":"#6366f1","selected":"#dfe4ff","selected_text":"#151a33","hover":"#eef1ff","console":"#172033","button":"#eef2f7","danger":"#c6284d","danger_border":"#a91f40","success":"#147a52","success_border":"#0e6543","disabled":"#e5e9f0"},
    "Ocean": {"bg":"#071a24","panel":"#0d2633","input":"#09202b","text":"#e8fbff","muted":"#8fb7c5","border":"#215064","accent":"#11a7c7","accent2":"#25c3e3","selected":"#185267","selected_text":"#ffffff","hover":"#123d4d","console":"#041118","button":"#123545","danger":"#8d304d","danger_border":"#c24a69","success":"#11664f","success_border":"#25a07e","disabled":"#183441"},
    "Graphite": {"bg":"#17191d","panel":"#22252a","input":"#1b1e22","text":"#f1f3f5","muted":"#a4abb5","border":"#3a4049","accent":"#f59e0b","accent2":"#fbbf24","selected":"#4a3d24","selected_text":"#fffaf0","hover":"#30343b","console":"#0e1013","button":"#2c3037","danger":"#8f304a","danger_border":"#c74b67","success":"#176044","success_border":"#2d8a66","disabled":"#30343a"},
    "Solarized": {"bg":"#002b36","panel":"#073642","input":"#002b36","text":"#eee8d5","muted":"#93a1a1","border":"#24545e","accent":"#b58900","accent2":"#cb9b00","selected":"#235967","selected_text":"#ffffff","hover":"#174852","console":"#001e26","button":"#10424d","danger":"#8c3b4d","danger_border":"#c25a6d","success":"#176044","success_border":"#2d8a66","disabled":"#19434d"},
}


def palette(name: str) -> QPalette:
    t = THEMES.get(name, THEMES["Midnight"])
    p = QPalette()
    p.setColor(QPalette.Window, QColor(t["bg"]))
    p.setColor(QPalette.WindowText, QColor(t["text"]))
    p.setColor(QPalette.Base, QColor(t["input"]))
    p.setColor(QPalette.AlternateBase, QColor(t["panel"]))
    p.setColor(QPalette.Text, QColor(t["text"]))
    p.setColor(QPalette.Button, QColor(t["button"]))
    p.setColor(QPalette.ButtonText, QColor(t["text"]))
    p.setColor(QPalette.Highlight, QColor(t["selected"]))
    p.setColor(QPalette.HighlightedText, QColor(t["selected_text"]))
    p.setColor(QPalette.PlaceholderText, QColor(t["muted"]))
    p.setColor(QPalette.ToolTipBase, QColor(t["panel"]))
    p.setColor(QPalette.ToolTipText, QColor(t["text"]))
    p.setColor(QPalette.Disabled, QPalette.Text, QColor(t["muted"]))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(t["muted"]))
    return p


def stylesheet(name: str) -> str:
    t = THEMES.get(name, THEMES["Midnight"])
    return f"""
QMainWindow, QWidget {{ background: {t['bg']}; color: {t['text']}; font-family: Segoe UI, Arial; font-size: 10pt; }}
QFrame#InfoCard {{ background: {t['selected']}; border: 1px solid {t['accent']}; border-radius: 12px; }}
QFrame#InnerCard {{ background: {t['input']}; border: 1px solid {t['border']}; border-radius: 10px; }}
QFrame#ActionCard {{ background: {t['panel']}; border: 1px solid {t['border']}; border-radius: 10px; }}
QGroupBox#FeatureGroup {{ background: {t['panel']}; border: 1px solid {t['border']}; border-radius: 12px; }}
QLabel#SectionLabel {{ color: {t['text']}; font-size: 9pt; font-weight: 700; letter-spacing: 0.5px; }}
QLabel#Badge {{ color: #ffffff; background: {t['accent']}; border-radius: 6px; padding: 4px 8px; font-size: 8pt; font-weight: 700; }}
QFrame#Card, QGroupBox {{ background: {t['panel']}; border: 1px solid {t['border']}; border-radius: 12px; }}
QGroupBox {{ margin-top: 14px; padding: 20px 14px 14px 14px; font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 14px; padding: 0 8px; color: {t['text']}; font-size: 9.5pt; font-weight: 700; }}
QLabel#Title {{ font-size: 24pt; font-weight: 700; color: {t['text']}; }}
QLabel#Subtitle, QLabel#Muted {{ color: {t['muted']}; }}
QLabel#MetricValue {{ color: {t['text']}; font-size: 12pt; font-weight: 700; }}
QLabel#MetricLabel {{ color: {t['muted']}; font-size: 8.5pt; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background: {t['input']}; border: 1px solid {t['border']}; border-radius: 8px; padding: 8px 9px; color: {t['text']}; min-height: 22px; selection-background-color: {t['selected']}; selection-color: {t['selected_text']}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border: 1px solid {t['accent']}; }}
QComboBox QAbstractItemView {{ background: {t['panel']}; color: {t['text']}; selection-background-color: {t['selected']}; selection-color: {t['selected_text']}; border: 1px solid {t['border']}; }}
QPushButton {{ background: {t['button']}; border: 1px solid {t['border']}; border-radius: 9px; padding: 8px 12px; font-weight: 600; min-height: 22px; color: {t['text']}; }}
QPushButton:hover {{ background: {t['hover']}; border-color: {t['accent']}; }}
QPushButton:pressed {{ background: {t['selected']}; }}
QPushButton:disabled {{ color: {t['muted']}; background: {t['disabled']}; border-color: {t['border']}; }}
QPushButton#Primary {{ background: {t['accent']}; border-color: {t['accent2']}; color: #ffffff; }}
QPushButton#Primary:hover {{ background: {t['accent2']}; }}
QPushButton#Danger {{ background: {t['danger']}; border-color: {t['danger_border']}; color: #ffffff; }}
QPushButton#Danger:hover {{ background: {t['danger_border']}; }}
QPushButton#Success {{ background: {t['success']}; border-color: {t['success_border']}; color: #ffffff; }}
QListWidget, QTableWidget {{ background: {t['input']}; color: {t['text']}; border: 1px solid {t['border']}; border-radius: 10px; gridline-color: {t['border']}; alternate-background-color: {t['panel']}; }}
QListWidget::item {{ background: {t['panel']}; color: {t['text']}; border: 1px solid {t['border']}; border-radius: 10px; padding: 10px; margin: 3px 5px; }}
QListWidget::item:hover {{ background: {t['hover']}; }}
QListWidget::item:selected {{ background: {t['selected']}; color: {t['selected_text']}; border-color: {t['accent']}; }}
QTableWidget::item {{ padding: 6px; color: {t['text']}; }}
QTableWidget::item:selected {{ background: {t['selected']}; color: {t['selected_text']}; }}
QHeaderView::section {{ background: {t['panel']}; color: {t['muted']}; padding: 8px; border: 0; border-bottom: 1px solid {t['border']}; }}
QPlainTextEdit, QTextEdit {{ background: {t['console']}; border: 1px solid {t['border']}; border-radius: 10px; color: {t['text']}; font-family: Consolas, monospace; font-size: 9pt; padding: 5px; selection-background-color: {t['selected']}; selection-color: {t['selected_text']}; }}
QProgressBar {{ background: {t['input']}; border: 1px solid {t['border']}; border-radius: 8px; min-height: 18px; text-align: center; color: {t['text']}; }}
QProgressBar::chunk {{ background: {t['accent']}; border-radius: 7px; }}
QCheckBox {{ spacing: 8px; min-height: 22px; color: {t['text']}; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {t['border']}; border-radius: 4px; background: {t['input']}; }}
QCheckBox::indicator:checked {{ background: {t['accent']}; border-color: {t['accent2']}; }}
QRadioButton {{ color: {t['text']}; }}
QTabWidget::pane {{ border: 1px solid {t['border']}; border-radius: 10px; top: -1px; }}
QTabBar::tab {{ background: {t['input']}; color: {t['muted']}; border: 1px solid {t['border']}; padding: 9px 14px; margin-right: 3px; border-radius: 7px; min-width: 72px; }}
QTabBar::tab:hover {{ background: {t['hover']}; color: {t['text']}; }}
QTabBar::tab:selected {{ background: {t['selected']}; color: {t['selected_text']}; border-color: {t['accent']}; }}
QSplitter::handle {{ background: {t['border']}; width: 4px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical, QScrollBar:horizontal {{ background: {t['bg']}; border: none; }}
QScrollBar:vertical {{ width: 11px; margin: 2px; }}
QScrollBar:horizontal {{ height: 11px; margin: 2px; }}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{ background: {t['border']}; min-height: 30px; min-width: 30px; border-radius: 5px; }}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{ background: {t['accent']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0px; height: 0px; }}
QToolTip {{ background: {t['panel']}; color: {t['text']}; border: 1px solid {t['accent']}; padding: 5px; }}
"""
