# part 1
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QScrollArea, QLabel, QPushButton)
from PySide6.QtCore import Qt, Signal
from typing import List, Dict,Optional


from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGridLayout,
    QScrollArea,
    QLabel,
    QPushButton
)
from PySide6.QtCore import Qt, Signal
from typing import Dict, List, Optional

class CardWidget(QWidget):
    clicked = Signal(object)

    def __init__(self, widget: QWidget, parent=None):
        super().__init__(parent)

        self.widget = widget
        self._selected = False

        self.setup_ui()

    def setup_ui(self):
        layout = QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        self.background_layer = QWidget(self)
        self.background_layer.setProperty("class", "card")

        layout.addWidget(self.background_layer, 0, 0)
        layout.addWidget(self.widget, 0, 0)

    def mousePressEvent(self, event):
        self.clicked.emit(self)
        super().mousePressEvent(event)

    def update_widget(self, widget):
        old_widget = self.widget

        self.layout().removeWidget(old_widget)
        old_widget.setParent(None)
        old_widget.deleteLater()

        self.widget = widget
        self.layout().addWidget(widget, 0, 0)

    def set_selected(self, selected: bool):
        self._selected = selected

        self.background_layer.setProperty(
            "class",
            "card-selected" if selected else "card"
        )

        self.background_layer.style().unpolish(self.background_layer)
        self.background_layer.style().polish(self.background_layer)
        self.background_layer.update()

        
class CardGridView(QWidget):

    card_selected = Signal(QWidget)
    card_removed = Signal(QWidget)
    load_more_requested = Signal()

    def __init__(self, columns=2, parent=None):
        super().__init__(parent)

        self.columns = max(1, columns)

        self.cards: Dict[int, CardWidget] = {}

        self.selected_card: Optional[CardWidget] = None

        self.has_more = True
        self.is_loading = False
        self.load_threshold = 100

        self.setup_ui()

    def setup_ui(self):

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        root_layout.addWidget(self.scroll_area)

        # Main scroll content
        self.container = QWidget()

        self.scroll_layout = QVBoxLayout(self.container)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(0)

        # Cards area
        self.cards_widget = QWidget()

        self.grid_layout = QGridLayout(self.cards_widget)
        self.grid_layout.setContentsMargins(3, 3, 3, 3)
        self.grid_layout.setSpacing(2)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_layout.addWidget(self.cards_widget)

        # Footer area
        self.footer_widget = QWidget()

        self.footer_layout = QVBoxLayout(self.footer_widget)
        self.footer_layout.setContentsMargins(0, 0, 0, 0)
        self.footer_layout.setSpacing(4)

        self.scroll_layout.addWidget(self.footer_widget)

        self.scroll_area.setWidget(self.container)

        # Scroll detection
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.valueChanged.connect(self.on_scroll_changed)

        # Loading label
        self.loading_label = QLabel("Loading more items...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.hide()

        self.footer_layout.addWidget(self.loading_label)

        # Load more button
        self.load_more_button = QPushButton("Load More")
        self.load_more_button.hide()
        self.load_more_button.clicked.connect(
            self.on_load_more_clicked
        )

        self.footer_layout.addWidget(self.load_more_button)

        # Empty label
        self.empty_label = QLabel("No results found.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()

        self.footer_layout.addWidget(self.empty_label)

    def _update_container_size(self):
        self.grid_layout.invalidate()
        self.cards_widget.adjustSize()
        self.container.adjustSize()

    def on_scroll_changed(self, value):

        if not self.has_more:
            return

        if self.is_loading:
            return

        scrollbar = self.scroll_area.verticalScrollBar()

        if scrollbar.maximum() - value <= self.load_threshold:
            self.load_next_page()

    def on_load_more_clicked(self):
        self.load_next_page()

    def load_next_page(self):

        if not self.has_more:
            return

        if self.is_loading:
            return

        self.show_loading_indicator()
        self.load_more_requested.emit()

    def show_loading_indicator(self):
        self.is_loading = True
        self.loading_label.show()
        self._update_container_size()

    def hide_loading_indicator(self):
        self.is_loading = False
        self.loading_label.hide()
        self._update_container_size()

    def show_load_more_button(self):
        self.load_more_button.show()
        self._update_container_size()

    def hide_load_more_button(self):
        self.load_more_button.hide()
        self._update_container_size()

    def show_empty_message(
        self,
        message: str = "No results found."
    ):
        self.empty_label.setText(message)
        self.empty_label.show()
        self._update_container_size()

    def hide_empty_message(self):
        self.empty_label.hide()
        self._update_container_size()

    def set_columns(self, columns: int):

        if columns < 1:
            raise ValueError(
                "Number of columns must be at least 1"
            )

        self.columns = columns
        self._reorganize_cards()

    def add_card(
        self,
        card_id: int,
        widget: QWidget
    ) -> CardWidget:

        if card_id in self.cards:
            raise ValueError(
                f"Card with ID {card_id} already exists"
            )

        card = CardWidget(widget)

        card.clicked.connect(self.select_card)

        index = len(self.cards)

        row = index // self.columns
        col = index % self.columns

        self.grid_layout.addWidget(card, row, col)

        self.cards[card_id] = card

        self.hide_empty_message()

        self._update_container_size()

        return card

    def update_card(
        self,
        card_id: int,
        widget: QWidget
    ) -> bool:

        card = self.cards.get(card_id)

        if card is None:
            return False

        card.update_widget(widget)

        self._update_container_size()

        return True

    def get_card(
        self,
        card_id: int
    ) -> Optional[QWidget]:

        card = self.cards.get(card_id)

        return None if card is None else card.widget

    def get_cards(self) -> List[QWidget]:
        return [card.widget for card in self.cards.values()]

    def reset(self):

        self.clear()

        self.has_more = True
        self.is_loading = False

        self.scroll_area.verticalScrollBar().setValue(0)

    def clear(self):

        for card in self.cards.values():

            self.grid_layout.removeWidget(card)

            card.setParent(None)
            card.deleteLater()

        self.cards.clear()

        self.selected_card = None

        self.hide_loading_indicator()
        self.hide_load_more_button()
        self.hide_empty_message()

        self._update_container_size()

    def remove_card(self, card_id: int) -> bool:

        card = self.cards.get(card_id)

        if card is None:
            return False

        removed_widget = card.widget

        if card is self.selected_card:
            self.selected_card = None

        self.grid_layout.removeWidget(card)

        card.setParent(None)
        card.deleteLater()

        del self.cards[card_id]

        self._reorganize_cards()

        self.card_removed.emit(removed_widget)

        self._update_container_size()

        return True

    def select_card(self, card: CardWidget):

        if self.selected_card is card:
            return

        if self.selected_card:
            self.selected_card.set_selected(False)

        card.set_selected(True)

        self.selected_card = card

        self.card_selected.emit(card.widget)

    def _reorganize_cards(self):

        cards = list(self.cards.values())

        for i, card in enumerate(cards):

            row = i // self.columns
            col = i % self.columns

            self.grid_layout.addWidget(
                card,
                row,
                col
            )

        self._update_container_size()
