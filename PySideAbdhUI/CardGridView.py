from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QScrollArea)
from PySide6.QtCore import Qt, Signal
from typing import List, Dict,Optional

#T = TypeVar('T', bound=QWidget)

# Individual card widget
class CardWidget(QWidget):
    clicked = Signal(QWidget)  # Signal emitted when card is clicked
    
    def __init__(self, widget: QWidget,background="#FFFFFF", parent=None):
        super().__init__(parent)
        self.widget = widget
        self.setup_ui(background)
        
    def setup_ui(self, background="#FFFFFF"):
        # Setup the card UI
        #self.setProperty('class','card')
        layout = QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        background_layer = QWidget()
        background_layer.setStyleSheet(f'background-color:{background};')
        layout.addWidget(background_layer,0,0,1,1)
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
    
    
class CardGridView(QWidget):
    # Custom widget for displaying cards in a grid layout
    
    # Signals
    card_selected = Signal(QWidget)  # Signal emitted when a card is selected
    card_removed = Signal(QWidget)   # Signal emitted when a card is removed
    
    def __init__(self,columns = 2, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.selected_card: Optional[CardWidget] = None
        self.cards: Dict[int, CardWidget] = {}  # Dictionary to track cards by ID
        self.columns = columns  # Default number of columns
        
    def setup_ui(self):
        """Setup the grid view UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Create container widget for grid
        container = QWidget()
        self.grid_layout = QGridLayout(container)
        self.grid_layout.setSpacing(2)
        self.grid_layout.setContentsMargins(2, 2, 2, 2)
        
        # Set scroll area widget
        scroll.setWidget(container)
        layout.addWidget(scroll)
        
    
    def set_columns(self, columns: int):
        """Set the number of columns in the grid"""
        if columns < 1:
            raise ValueError("Number of columns must be at least 1")
        self.columns = columns
        self._reorganize_cards()
    
    def add_card(self, card_id: int, widget: QWidget) -> CardWidget:
        # Add a new card to the grid with any widget 
        if card_id in self.cards:
            raise ValueError(f"Card with ID {card_id} already exists")
        
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
    
    def remove_card(self, card_id: int) -> bool:
        """Remove a card by ID"""
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
        return True
    
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
    
    def get_cards(self) -> List[QWidget]:
        """Get all card widgets"""
        return [card.widget for card in self.cards.values()]
    
    def clear(self):
        """Clear all cards from the grid"""
        for card_id in list(self.cards.keys()):
            self.remove_card(card_id)
    
    def select_card(self, card: CardWidget):
        # Handle card selection
        old = self.get_selected_card()
        if self.selected_card:

            self.selected_card.setStyleSheet("border:2px solid transparent;")
        
        card.setProperty('class','card')
        card.setStyleSheet(r"QWidget.card{border:5px solid #1a73e8;}")
        self.selected_card = card
        self.card_selected.emit(card.widget)
    
    def get_selected_card(self) -> Optional[QWidget]:
        """Get the currently selected card widget"""
        return self.selected_card.widget if self.selected_card else None
    
    def _reorganize_cards(self):
        """Reorganize cards in the grid after removal"""
        cards = list(self.cards.values())
        for i, card in enumerate(cards):
            row = i // self.columns
            col = i % self.columns
            self.grid_layout.addWidget(card, row, col) 