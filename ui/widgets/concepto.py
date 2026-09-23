"""
El campo donde se escribe un concepto.

Es un cuadro de texto de varias líneas —un trabajo se describe entero, no cabe
en un renglón— con sugerencias de lo ya escrito otras veces. Sugiere, nunca
obliga: se acepta con Tab o Intro, y se ignora simplemente siguiendo a
escribir.
"""

from PyQt6.QtCore import Qt, QStringListModel
from PyQt6.QtWidgets import QCompleter, QPlainTextEdit


class CampoConcepto(QPlainTextEdit):
    """Cuadro de texto con autocompletado sobre los conceptos ya usados."""

    def __init__(self, sugerencias=(), parent=None):
        super().__init__(parent)
        self.setTabChangesFocus(True)
        self.setPlaceholderText(
            "Describe el trabajo: «Suministro y montaje de armario empotrado de "
            "dos módulos con puerta corredera, 2,00 × 2,40 m…»"
        )

        self._completer = QCompleter(self)
        self._completer.setModel(QStringListModel(list(sugerencias), self._completer))
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setWidget(self)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._completer.activated.connect(self._poner_sugerencia)

    def sugerencias(self, valores):
        self._completer.setModel(QStringListModel(list(valores), self._completer))

    def texto(self):
        return self.toPlainText().strip()

    def _poner_sugerencia(self, texto):
        """Al aceptar una sugerencia se sustituye el concepto entero."""
        self.setPlainText(texto)
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.setTextCursor(cursor)

    def keyPressEvent(self, evento):
        emergente = self._completer.popup()
        if emergente.isVisible() and evento.key() in (
            Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Tab,
            Qt.Key.Key_Escape, Qt.Key.Key_Up, Qt.Key.Key_Down,
        ):
            # Mientras la lista está abierta, estas teclas son suyas.
            evento.ignore()
            return

        super().keyPressEvent(evento)

        escrito = self.toPlainText().strip()
        if len(escrito) < 3:
            emergente.hide()
            return

        self._completer.setCompletionPrefix(escrito)
        if self._completer.completionCount() == 0:
            emergente.hide()
            return
        # Si lo único que sugiere es exactamente lo ya escrito, no molesta.
        if (self._completer.completionCount() == 1
                and self._completer.currentCompletion().lower() == escrito.lower()):
            emergente.hide()
            return

        emergente.setCurrentIndex(self._completer.completionModel().index(0, 0))
        rect = self.cursorRect()
        rect.setWidth(
            emergente.sizeHintForColumn(0) + emergente.verticalScrollBar().sizeHint().width()
        )
        self._completer.complete(rect)
