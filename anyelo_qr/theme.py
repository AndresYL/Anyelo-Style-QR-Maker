"""Hoja de estilos de toda la app. Los colores salen de brand.py."""
from . import brand
from .paths import asset


def build_qss() -> str:
    check = asset("check.png").as_posix()
    return f"""
* {{ font-family: "Segoe UI", "Inter", sans-serif; font-size: 13px; color: {brand.TEXT}; }}
QMainWindow, QWidget#root {{ background: {brand.BG}; }}
QDialog, QMessageBox {{ background: {brand.PANEL}; }}
QToolTip {{ background: {brand.PANEL_2}; color: {brand.TEXT}; border: 1px solid {brand.BORDER}; padding: 4px; }}
QMenu {{ background: {brand.PANEL_2}; border: 1px solid {brand.BORDER}; border-radius: 8px; padding: 6px; }}
QMenu::item {{ padding: 8px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: #33363A; }}
QMenu::separator {{ height: 1px; background: {brand.BORDER}; margin: 4px 8px; }}

QTabWidget::pane {{ border: none; background: transparent; top: -1px; }}
QTabBar::tab {{ background: transparent; color: {brand.MUTED}; padding: 9px 18px; margin-right: 2px; border: none; font-weight: 600; }}
QTabBar::tab:selected {{ color: {brand.TEXT}; border-bottom: 2px solid {brand.ACCENT}; }}
QTabBar::tab:hover:!selected {{ color: {brand.TEXT}; }}

QFrame#panel {{ background: {brand.PANEL}; border: 1px solid {brand.BORDER}; border-radius: 12px; }}
QFrame#step {{ background: {brand.PANEL}; border: 1px solid {brand.BORDER}; border-radius: 12px; }}
QLabel#badge {{ background: {brand.ACCENT}; color: {brand.ACCENT_TEXT}; border-radius: 13px; font-weight: 800; }}
QLabel#stepTitle {{ font-size: 15px; font-weight: 700; }}
QLabel#muted {{ color: {brand.MUTED}; }}
QLabel#h1 {{ font-size: 20px; font-weight: 700; }}
QLabel#h2 {{ font-size: 11px; font-weight: 700; color: {brand.MUTED}; letter-spacing: 1px; }}
QLabel#good {{ color: {brand.OK}; font-weight: 600; }}
QLabel#bad {{ color: {brand.WARN}; font-weight: 600; }}
QLabel#warn {{ color: {brand.WARN}; }}

QPlainTextEdit, QLineEdit, QComboBox, QTableWidget, QSpinBox, QKeySequenceEdit {{
    background: {brand.PANEL_2}; border: 1px solid {brand.BORDER}; border-radius: 8px; padding: 6px; selection-background-color: #3A3D41; }}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {brand.MUTED}; }}
QComboBox QAbstractItemView {{ background: {brand.PANEL_2}; selection-background-color: #3A3D41; border: 1px solid {brand.BORDER}; }}
QHeaderView::section {{ background: {brand.PANEL}; color: {brand.MUTED}; border: none; padding: 6px; font-weight: 600; }}
QTableWidget {{ gridline-color: {brand.BORDER}; }}

QPushButton {{ background: {brand.PANEL_2}; border: 1px solid {brand.BORDER}; border-radius: 8px; padding: 8px 14px; font-weight: 600; }}
QPushButton:hover {{ border-color: {brand.MUTED}; }}
QPushButton:disabled {{ color: #5A5E63; }}
QPushButton#primary {{ background: {brand.ACCENT}; color: {brand.ACCENT_TEXT}; border: none; padding: 10px 22px; }}
QPushButton#primary:hover {{ background: #E4E4E4; }}
QPushButton#primary:disabled {{ background: #3A3D41; color: #7A7E83; }}
QPushButton#link {{ background: transparent; border: none; color: {brand.MUTED}; padding: 4px 6px; font-weight: 500; }}
QPushButton#link:hover {{ color: {brand.TEXT}; text-decoration: underline; }}
QPushButton#chip {{ border-radius: 14px; padding: 5px 12px; font-weight: 500; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {brand.MUTED}; background: {brand.PANEL_2}; }}
QCheckBox::indicator:checked {{ background: {brand.ACCENT}; border-color: {brand.ACCENT}; image: url({check}); }}
QSlider::groove:horizontal {{ height: 4px; background: {brand.BORDER}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {brand.ACCENT}; width: 14px; margin: -6px 0; border-radius: 7px; }}
QProgressBar {{ background: {brand.PANEL_2}; border: none; border-radius: 4px; height: 8px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {brand.ACCENT}; border-radius: 4px; }}

QScrollArea {{ background: transparent; border: none; }}
QWidget#scrollViewport, QWidget#scrollPage {{ background: transparent; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 0px; height: 0px; border: none; margin: 0; padding: 0; }}
QSpinBox QLineEdit {{ background: transparent; border: none; padding: 0; margin: 0; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {brand.BORDER}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QLabel#drop {{ border: 2px dashed {brand.BORDER}; border-radius: 12px; color: {brand.MUTED}; padding: 26px; }}
QLabel#drop[hover="true"] {{ border-color: {brand.ACCENT}; color: {brand.TEXT}; }}

QFrame#menuCard {{ background: {brand.PANEL}; border: 1px solid {brand.MUTED}; border-radius: 16px; }}
QPushButton#choice {{ background: {brand.PANEL_2}; border: 1px solid {brand.BORDER}; border-radius: 12px; padding: 0; text-align: left; }}
QPushButton#choice:hover {{ border-color: {brand.ACCENT}; background: #26292C; }}
QLabel#choiceTitle {{ font-size: 15px; font-weight: 700; background: transparent; }}
QLabel#choiceSub {{ color: {brand.MUTED}; background: transparent; }}
QLabel#choiceKey {{ background: {brand.BORDER}; border-radius: 6px; font-weight: 700; color: {brand.TEXT}; }}
QFrame#resultCard {{ background: {brand.PANEL_2}; border: 1px solid {brand.BORDER}; border-radius: 10px; }}
"""
