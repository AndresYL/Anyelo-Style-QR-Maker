"""Hoja de estilos de toda la app. Los valores salen del tema de la página (brand.py).
La tipografía se asigna en Python (fonts.py), no aquí, para que cada peso sea exacto."""
from . import brand
from .paths import asset


def build_qss() -> str:
    check = asset("check.png").as_posix()
    chevron = asset("chevron.png").as_posix()
    b = brand
    return f"""
QWidget {{ color: {b.BONE}; selection-background-color: {b.RED}; selection-color: {b.BONE}; }}
QMainWindow, QWidget#root {{ background: {b.INK}; }}
QDialog, QMessageBox {{ background: {b.SURFACE}; }}
QToolTip {{ background: {b.INK}; color: {b.BONE}; border: 1px solid {b.GOLD}; padding: 6px 10px; }}
QMenu {{ background: {b.PANEL}; border: 1px solid {b.LINE_2}; padding: 6px; }}
QMenu::item {{ padding: 9px 22px; }}
QMenu::item:selected {{ background: #1F1B10; color: {b.GOLD}; }}
QMenu::separator {{ height: 1px; background: {b.LINE}; margin: 5px 8px; }}

/* riel lateral */
QFrame#rail {{ background: #050505; border-right: 1px solid {b.LINE}; }}
QFrame#panelSide {{ background: {b.SURFACE}; border-left: 1px solid {b.LINE}; }}

/* tarjetas de paso */
QFrame#step {{ background: {b.SURFACE}; border: 1px solid {b.LINE}; }}
QFrame#resultCard {{ background: {b.PANEL}; border: 1px solid {b.LINE}; }}
QFrame#drop {{ background: {b.SURFACE}; border: 1px dashed {b.LINE_2}; }}
QFrame#drop[hover="true"] {{ border-color: {b.GOLD}; background: #121008; }}

/* campos */
QLineEdit, QPlainTextEdit, QSpinBox, QComboBox {{
    background: #0A0A0A; border: 1px solid {b.LINE_2}; border-radius: 0; padding: 9px 12px; color: {b.BONE}; }}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {b.GOLD}; }}
QLineEdit:read-only {{ color: {b.BONE_DIM}; }}
QPlainTextEdit {{ padding: 12px 14px; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 0px; height: 0px; border: none; margin: 0; padding: 0; }}
QSpinBox QLineEdit {{ background: transparent; border: none; padding: 0; margin: 0; }}
QComboBox {{ padding-right: 34px; }}
QComboBox::drop-down {{ border: none; width: 32px; }}
QComboBox::down-arrow {{ image: url({chevron}); width: 14px; height: 9px; }}
QComboBox QAbstractItemView {{ background: {b.PANEL}; border: 1px solid {b.LINE_2}; padding: 4px; outline: 0;
    selection-background-color: #1F1B10; selection-color: {b.GOLD}; }}
QComboBox QAbstractItemView::item {{ padding: 8px 10px; min-height: 22px; }}

/* botones */
QPushButton#pill {{ background: transparent; color: {b.BONE_DIM}; border: 1px solid {b.LINE_2}; border-radius: 17px;
    padding: 0 18px; min-height: 34px; }}
QPushButton#pill:hover {{ background: {b.BONE}; color: {b.INK}; border-color: {b.BONE}; }}
QPushButton#pill:pressed {{ background: {b.CREAM}; color: {b.INK}; }}
QPushButton#pill:disabled {{ color: #55524A; border-color: {b.LINE}; background: transparent; }}
QPushButton#link {{ background: transparent; border: none; color: {b.MUTED}; padding: 6px 4px; }}
QPushButton#link:hover {{ color: {b.GOLD}; }}
QPushButton#recorder {{ background: #0A0A0A; border: 1px solid {b.LINE_2}; color: {b.BONE}; padding: 0 18px; text-align: center; }}
QPushButton#recorder:hover {{ border-color: {b.MUTED}; }}
QPushButton#recorder[recording="true"] {{ border-color: {b.GOLD}; color: {b.GOLD}; background: #121008; }}

/* casillas y deslizador */
QCheckBox {{ spacing: 9px; background: transparent; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {b.MUTED}; background: #0A0A0A; border-radius: 0; }}
QCheckBox::indicator:hover {{ border-color: {b.BONE}; }}
QCheckBox::indicator:checked {{ background: {b.GOLD}; border-color: {b.GOLD}; image: url({check}); }}
QSlider::groove:horizontal {{ height: 2px; background: {b.LINE_2}; }}
QSlider::sub-page:horizontal {{ background: {b.GOLD}; }}
QSlider::handle:horizontal {{ background: {b.BONE}; width: 14px; height: 14px; margin: -6px 0; border-radius: 7px; }}
QSlider::handle:horizontal:disabled {{ background: {b.LINE_2}; }}
QSlider::sub-page:horizontal:disabled {{ background: {b.LINE_2}; }}
QProgressBar {{ background: {b.LINE}; border: none; max-height: 3px; min-height: 3px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {b.GOLD}; }}

/* tablas */
QTableWidget {{ background: transparent; color: {b.BONE}; gridline-color: {b.LINE}; border: none; outline: 0; }}
QTableWidget::item {{ border-bottom: 1px solid {b.LINE}; padding: 0 10px; }}
QTableWidget::item:selected {{ background: #1F1B10; color: {b.GOLD}; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{ background: transparent; color: {b.MUTED}; border: none; border-bottom: 1px solid {b.LINE_2};
    padding: 8px 10px; text-align: left; }}
QTableCornerButton::section {{ background: transparent; border: none; }}

/* scroll */
QScrollArea {{ background: transparent; border: none; }}
QWidget#scrollViewport, QWidget#scrollPage {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {b.LINE_2}; min-height: 36px; margin: 2px; border-radius: 3px; }}
QScrollBar::handle:vertical:hover {{ background: {b.MUTED}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {b.LINE_2}; min-width: 36px; margin: 2px; border-radius: 3px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* menú del atajo y resultados del escaneo */
QFrame#menuCard {{ background: {b.SURFACE}; border: 1px solid {b.LINE_2}; }}
QPushButton#choice {{ background: transparent; border: none; border-left: 3px solid transparent; text-align: left; padding: 0; }}
QPushButton#choice:hover {{ background: #15130B; border-left-color: {b.GOLD}; }}
QLabel#choiceTitle, QLabel#choiceSub, QLabel#choiceKey {{ background: transparent; }}
"""
