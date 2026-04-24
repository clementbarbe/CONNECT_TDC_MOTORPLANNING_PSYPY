# tabs/tabs_handrepresentation.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QHBoxLayout,
    QLabel, QComboBox, QPushButton,
)


class HandRepresentationTab(QWidget):
    """Tab for the Hand Representation task (no calibration here)."""

    BLOCK_MAP = {
        "Block 1 Pre":  ("1", 1),
        "Block 2 Pre":  ("2", 2),
        "Block 3 Post": ("3", 3),
    }

    def __init__(self, parent_menu):
        super().__init__()
        self.parent_menu = parent_menu
        self.init_ui()

    # =========================================================================
    # UI BUILD
    # =========================================================================

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        layout.addWidget(self._build_hand_group())
        layout.addWidget(self._build_block_group())
        layout.addWidget(self._build_launch_group())
        layout.addStretch()

    def _build_hand_group(self):
        group = QGroupBox("Main testée")
        hbox  = QHBoxLayout()

        hbox.addWidget(QLabel("Main :"))
        self.combo_hand = QComboBox()
        self.combo_hand.addItems(["droite", "gauche"])
        hbox.addWidget(self.combo_hand)
        hbox.addStretch()

        group.setLayout(hbox)
        return group

    def _build_block_group(self):
        group = QGroupBox("Block (100 trials)")
        hbox  = QHBoxLayout()

        hbox.addWidget(QLabel("Block :"))
        self.combo_block = QComboBox()
        self.combo_block.addItems(list(self.BLOCK_MAP.keys()))
        hbox.addWidget(self.combo_block)
        hbox.addStretch()

        group.setLayout(hbox)
        return group

    def _build_launch_group(self):
        group = QGroupBox("Lancement")
        vbox  = QVBoxLayout()

        btn = QPushButton("Lancer Hand Representation")
        btn.clicked.connect(self.run_task)
        vbox.addWidget(btn)

        group.setLayout(vbox)
        return group

    # =========================================================================
    # HELPERS
    # =========================================================================

    def get_common(self):
        block_label            = self.combo_block.currentText()
        session_str, block_num = self.BLOCK_MAP[block_label]

        return {
            "tache":          "HandRepresentation",
            "session":        session_str,
            "block_label":    block_label,
            "block_number":   block_num,
            "hand":           self.combo_hand.currentText(),
            "n_blocks":       1,
            "trial_duration": 4.0,
            "camera_index":   0,
        }

    # =========================================================================
    # LAUNCH
    # =========================================================================

    def run_task(self):
        self.parent_menu.run_experiment(self.get_common())