# tabs_handrepresentation.py
"""
PyQt6 control panel for HandRepresentationTask
----------------------------------------------
Menu très simple :
    - choix latéralité : gaucher / droitier
    - choix block : Block 1 Pre / Block 2 Pre / Block 3 Post
    - lancement de la tâche
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QComboBox, QMessageBox
)


def _label(text: str) -> QLabel:
    return QLabel(text)


class HandRepresentationTab(QWidget):

    def __init__(self, parent_menu):
        super().__init__()
        self.parent_menu = parent_menu
        self._init_ui()

    # ─────────────────────────────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────────────────────────────

    def _init_ui(self):
        root = QVBoxLayout()
        root.setSpacing(12)
        self.setLayout(root)

        root.addWidget(self._build_subject_group())
        root.addWidget(self._build_block_group())
        root.addWidget(self._build_launch_group())

        self.lbl_info = QLabel(
            "1 block = 100 trials\n"
            "Chaque block contient 10 miniblocks randomisés des 10 positions."
        )
        self.lbl_info.setStyleSheet("color: #2196F3; font-weight: bold;")
        self.lbl_info.setWordWrap(True)
        root.addWidget(self.lbl_info)

        root.addStretch()

    # ── Subject / handedness ────────────────────────────────────────────

    def _build_subject_group(self) -> QGroupBox:
        grp = QGroupBox("🖐️ Main testée")
        grid = QGridLayout()
        grid.setColumnStretch(2, 1)

        grid.addWidget(_label("Latéralité / main :"), 0, 0)

        self.combo_handedness = QComboBox()
        self.combo_handedness.addItems(["droitier", "gaucher"])
        self.combo_handedness.setMinimumWidth(140)
        grid.addWidget(self.combo_handedness, 0, 1)

        grid.addWidget(
            _label("Sélectionne la condition correspondant à la main testée."),
            0, 2
        )

        grp.setLayout(grid)
        return grp

    # ── Block selection ────────────────────────────────────────────────

    def _build_block_group(self) -> QGroupBox:
        grp = QGroupBox("📦 Block")
        grid = QGridLayout()
        grid.setColumnStretch(2, 1)

        grid.addWidget(_label("Choix du block :"), 0, 0)

        self.combo_block = QComboBox()
        self.combo_block.addItems([
            "Block 1 Pre",
            "Block 2 Pre",
            "Block 3 Post",
        ])
        self.combo_block.setMinimumWidth(160)
        grid.addWidget(self.combo_block, 0, 1)

        grid.addWidget(
            _label("Les 3 blocks ont le même contenu, seul le nom change."),
            0, 2
        )

        grp.setLayout(grid)
        return grp

    # ── Launch ─────────────────────────────────────────────────────────

    def _build_launch_group(self) -> QGroupBox:
        grp = QGroupBox("🚀 Lancement")
        layout = QVBoxLayout()

        btn = QPushButton("📸 Lancer Hand Representation")
        btn.setMinimumHeight(48)
        btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; "
            "font-weight: bold; border-radius: 4px; padding: 6px 16px; "
            "font-size: 14px; }"
            "QPushButton:hover { background-color: #43A047; }"
        )
        btn.clicked.connect(self.run_task)
        layout.addWidget(btn)

        grp.setLayout(layout)
        return grp

    # ─────────────────────────────────────────────────────────────────────
    # PARAMS
    # ─────────────────────────────────────────────────────────────────────

    def _get_params(self) -> dict:
        block_label = self.combo_block.currentText()

        # mapping simple vers un numéro de block
        block_map = {
            "Block 1 Pre": 1,
            "Block 2 Pre": 2,
            "Block 3 Post": 3,
        }

        return {
            "tache": "HandRepresentation",
            "handedness": self.combo_handedness.currentText(),   # droitier / gaucher
            "block_label": block_label,                          # nom affiché
            "block_number": block_map[block_label],             # 1 / 2 / 3
            "n_blocks": 1,                                      # un lancement = un block
            "trial_duration": 7.0,
            "camera_index": 0,
        }

    def _confirm_launch(self) -> bool:
        params = self._get_params()

        reply = QMessageBox.question(
            self,
            "Confirmer le lancement",
            f"Hand Representation\n\n"
            f"Main : {params['handedness']}\n"
            f"Block : {params['block_label']}\n"
            f"Durée : 100 trials × 7 s\n\n"
            f"Lancer ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    # ─────────────────────────────────────────────────────────────────────
    # LAUNCH
    # ─────────────────────────────────────────────────────────────────────

    def run_task(self):
        if not self._confirm_launch():
            return

        params = self._get_params()
        self.parent_menu.run_experiment(params)