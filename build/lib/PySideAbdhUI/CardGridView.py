from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QScrollArea, QLabel, QPushButton)
from PySide6.QtCore import Qt, Signal
from typing import List, Dict,Optional

# Individual card widget
class CardWidget(QWidget):
    clicked = Signal(QWidget)  # Signal emitted when card is clicked
    
    def __init__(self, widget: QWidget, parent=None):
        super().__init__(parent)
        # user defined view
        self.widget = widget
        self._selected = False
        self.setup_ui()
        
    def setup_ui(self):
        # Setup the card UI
        layout = QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        self.background_layer = QWidget()
        self.background_layer.setProperty('class','card')
        layout.addWidget(self.background_layer,0,0,1,1)
        # Add the widget to the layout
        layout.addWidget(self.widget,0,0,1,1)
        
        # Add click event
        self.mousePressEvent = self._on_click
    
    def _on_click(self, event):
        # Handle click event
        self.clicked.emit(self)
    
    def update_widget(self, widget: QWidget):
        # Update card widget
        # Remove old widget
        old_widget = self.widget
        self.layout().removeWidget(old_widget)
        old_widget.deleteLater()
        
        # Add new widget
        self.widget = widget
        self.layout().addWidget(widget)
    
    def toggle_selection(self):

        self._selected = not self._selected
        
        if self._selected: self.background_layer.setProperty('class','card-selected')
        
        else: self.background_layer.setProperty('class','card')
        # update the style of the card
        self.background_layer.style().unpolish(self.background_layer)
        self.background_layer.style().polish(self.background_layer)

class CardGridView(QWidget):
    # Custom widget for displaying cards in a grid layout
    
    # Signals
    card_selected = Signal(QWidget)  # Signal emitted when a card is selected
    card_removed = Signal(QWidget)   # Signal emitted when a card is removed
    load_more_requested = Signal()  # Emitted when user scrolls to bottom or clicks "Load More"
    
    def __init__(self,columns = 2, parent=None):
        super().__init__(parent)
        
        self.setup_ui()
        
        self.selected_card: Optional[CardWidget] = None
        
        self.cards: Dict[int, CardWidget] = {}  # Dictionary to track cards by ID
        
        self.columns = columns                  # Default number of columns
        
        self.has_more = True          # Controlled by parent
        
        self.is_loading = False
        
        self.load_threshold = 100     # Pixels from bottom to trigger load

    
    def setup_ui(self):
        """Setup the grid view UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Create container widget for grid
        container = QWidget()
        container.setProperty('class','surface-background-layer')
        self.grid_layout = QGridLayout(container)

        self.grid_layout.setSpacing(2)
        self.grid_layout.setContentsMargins(3, 3, 3, 3)
        
        # Set scroll area widget
        self.scroll_area.setWidget(container)
        layout.addWidget(self.scroll_area)
        
        #### New #################################################
        # Connect scroll event
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.valueChanged.connect(self.on_scroll_changed)
        
        # Loading indicator
        self.loading_label = QLabel("Loading more items...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet("color: gray; font-size: 14px; padding: 20px;")
        self.loading_label.hide()

        # Load More button (optional fallback)
        self.load_more_button = QPushButton("Load More")
        self.load_more_button.setCursor(Qt.CursorShape.PointingHandCursor)
        #self.load_more_button.clicked.connect(self.on_load_more_clicked)
        self.load_more_button.hide()

        # Empty state label
        self.empty_label = QLabel("No results found.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: gray; font-size: 18px; padding: 50px;")
        self.empty_label.hide()

    
    def on_scroll_changed(self, value):
        if not self.has_more or self.is_loading: return

        scrollbar = self.scroll_area.verticalScrollBar()
        # Trigger when close to bottom
        if scrollbar.maximum() - value <= self.load_threshold:
            self.load_next_page()

    def on_load_more_clicked(self): self.load_next_page()

    def load_next_page(self):
        """Called when more data should be loaded"""
        if self.has_more and not self.is_loading:
            self.show_loading_indicator()
            self.load_more_requested.emit()
    
    def show_loading_indicator(self):
        if self.loading_label.parent() is None:
            # Span full columns
            row = self.grid_layout.rowCount()
            self.grid_layout.addWidget(self.loading_label, row, 0, 1, self.columns)
        self.loading_label.show()
        self.is_loading = True

    def hide_loading_indicator(self):
        self.loading_label.hide()
        self.is_loading = False

    def show_load_more_button(self):
        if self.load_more_button.parent() is None:
            row = self.grid_layout.rowCount()
            self.grid_layout.addWidget(self.load_more_button, row, 0, 1, self.columns)
        self.load_more_button.show()

    def hide_load_more_button(self): self.load_more_button.hide()
    
    def show_empty_message(self, message: str = "No results found."):
        self.empty_label.setText(message)
        if self.empty_label.parent() is None:
            row = self.grid_layout.rowCount()
            self.grid_layout.addWidget(self.empty_label, row, 0, 1, self.columns)
        self.empty_label.show()

    def hide_empty_message(self): self.empty_label.hide()

    def set_columns(self, columns: int):
        """Set the number of columns in the grid"""
        if columns < 1:
            raise ValueError("Number of columns must be at least 1")
        self.columns = columns
        self._reorganize_cards()
    
    def add_card(self, card_id: int, widget: QWidget) -> CardWidget:
        # Add a new card to the grid with any widget 
        if card_id in self.cards: raise ValueError(f"Card with ID {card_id} already exists")
        
        card = CardWidget(widget)
        card.clicked.connect(self.select_card)
        
        # Calculate position
        current_count = len(self.cards)
        row = current_count // self.columns
        col = current_count % self.columns
        
        # Add to grid
        self.grid_layout.addWidget(card, row, col,1,1)
        self.cards[card_id] = card
        
        return card

    def update_card(self, card_id: int, widget: QWidget) -> bool:
        """Update an existing card's widget"""
        if card_id not in self.cards:
            return False
        
        card = self.cards[card_id]
        card.update_widget(widget)
        return True
    
    def get_card(self, card_id: int) -> Optional[QWidget]:
        """Get card widget by ID"""
        if card_id not in self.cards:
            return None
        return self.cards[card_id].widget
    
    #Get all card widgets
    def get_cards(self) -> List[QWidget]: return [card.widget for card in self.cards.values()]
    
    # Optional: reset state when starting a new search
    def reset(self):
        self.clear()
        self.has_more = True
        self.is_loading = False
        self.scroll_area.verticalScrollBar().setValue(0)

    def clear(self):
        # Remove all cards
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
                item.widget().deleteLater()

        self.selected_card = None
        # Reset UI elements
        self.hide_loading_indicator()
        self.hide_load_more_button()
        self.hide_empty_message()
    
    def remove_card(self, card_id: int) -> bool:
        # Remove a card by ID
        if card_id not in self.cards:
            return False
        
        card = self.cards[card_id]
        if card == self.selected_card:
            self.selected_card = None
        
        # Remove from grid
        self.grid_layout.removeWidget(card)
        card.deleteLater()
        del self.cards[card_id]
        
        # Reorganize remaining cards
        self._reorganize_cards()
        
        # Emit signal
        self.card_removed.emit(card.widget)

        # Reset UI elements
        self.hide_loading_indicator()
        self.hide_load_more_button()
        self.hide_empty_message()

        return True

    def select_card(self, card: CardWidget):
        # Handle card selection
        if self.selected_card:
            self.selected_card.toggle_selection()

        card.toggle_selection()
        self.selected_card = card
        self.card_selected.emit(card.widget)
    
    #def get_selected_card(self) -> Optional[QWidget]:
    #    """Get the currently selected card widget"""
    #    return self.selected_card.widget if self.selected_card else None
    
    def _reorganize_cards(self):
        """Reorganize cards in the grid after removal"""
        cards = list(self.cards.values())
        for i, card in enumerate(cards):
            row = i // self.columns
            col = i % self.columns
            self.grid_layout.addWidget(card, row, col) 


"""
class CardGridView00(QWidget):
    load_more_requested = Signal()  # Emitted when user scrolls to bottom or clicks "Load More"
    # Signals
    card_selected = Signal(QWidget)  # Signal emitted when a card is selected
    card_removed = Signal(QWidget)   # Signal emitted when a card is removed
          
    def __init__(self, columns: int = 4, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setup_ui()
        self.selected_card: Optional[CardWidget] = None
        self.cards: Dict[int, CardWidget] = {}  # Dictionary to track cards by ID
        self.columns = columns                  # Default number of columns
        self.has_more = True          # Controlled by parent
        self.is_loading = False
        self.load_threshold = 100     # Pixels from bottom to trigger load

        self.setup_ui()

    def setup_ui(self):
        # Setup the grid view UI
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        #layout.setSpacing(10)

         # Create scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Create container widget for grid
        container = QWidget()
        container.setProperty('class','surface-background-layer')
        self.grid_layout = QGridLayout(container)
        # Container for grid
        #self.container = QWidget()
        # Set scroll area widget
        self.scroll_area.setWidget(container)
        layout.addWidget(self.scroll_area)

        # Connect scroll event
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.valueChanged.connect(self.on_scroll_changed)
        
        # Loading indicator
        self.loading_label = QLabel("Loading more items...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet("color: gray; font-size: 14px; padding: 20px;")
        self.loading_label.hide()

        # Load More button (optional fallback)
        self.load_more_button = QPushButton("Load More")
        self.load_more_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.load_more_button.clicked.connect(self.on_load_more_clicked)
        self.load_more_button.hide()

        # Empty state label
        self.empty_label = QLabel("No results found.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: gray; font-size: 18px; padding: 50px;")
        self.empty_label.hide()

    #def select_card(self, card: CardWidget):
    #    # Handle card selection
    #    if self.selected_card:
    #        self.selected_card.toggle_selection()

    #    card.toggle_selection()
    #    self.selected_card = card
    #    self.card_selected.emit(card.widget)

    # def clear(self):
    #    Remove all cards
    #    while self.grid_layout.count():
    #        item = self.grid_layout.takeAt(0)
    #        if item.widget():
    #            item.widget().setParent(None)
    #            item.widget().deleteLater()
    #
    #    # Reset UI elements
    #    self.hide_loading_indicator()
    #    self.hide_load_more_button()
    #    self.hide_empty_message()

    
    # ------------------- Infinite Scroll Detection -------------------
    # def on_scroll_changed(self, value):
    #    if not self.has_more or self.is_loading:
    #        return

    #    scrollbar = self.scroll_area.verticalScrollBar()
    #    # Trigger when close to bottom
    #    if scrollbar.maximum() - value <= self.load_threshold:
    #        self.load_next_page()

    # def on_load_more_clicked(self):
    #    self.load_next_page()

    # def load_next_page(self):
    #    Called when more data should be loaded
    #    if self.has_more and not self.is_loading:
    #        self.show_loading_indicator()
    #        self.load_more_requested.emit()
    
    # def select_card(self, card: CardWidget):
    #    # Handle card selection
    #    if self.selected_card:
    #        self.selected_card.toggle_selection()
    #
    #    card.toggle_selection()
    #    self.selected_card = card
    #    self.card_selected.emit(card.widget)

    # def show_loading_indicator(self):
    #    if self.loading_label.parent() is None:
    #        # Span full columns
    #        row = self.grid_layout.rowCount()
    #        self.grid_layout.addWidget(self.loading_label, row, 0, 1, self.columns)
    #    self.loading_label.show()
    #    self.is_loading = True

    #def hide_loading_indicator(self):
    #    self.loading_label.hide()
    #    self.is_loading = False

    # def show_load_more_button(self):
    #    if self.load_more_button.parent() is None:
    #        row = self.grid_layout.rowCount()
    #        self.grid_layout.addWidget(self.load_more_button, row, 0, 1, self.columns)
    #    self.load_more_button.show()

    # def hide_load_more_button(self):
    #    self.load_more_button.hide()
    
    # def show_empty_message(self, message: str = "No results found."):
    #    self.empty_label.setText(message)
    #    if self.empty_label.parent() is None:
    #        row = self.grid_layout.rowCount()
    #        self.grid_layout.addWidget(self.empty_label, row, 0, 1, self.columns)
    #    self.empty_label.show()

    #def hide_empty_message(self):
    #    self.empty_label.hide()

"""
