import QtQuick 2.15
import theme 1.0

// Bandeau de statut : libellé d'état.
// Purement visuel, sans visualiseur audio.
Column {
    id: root

    property string sphereState: "idle"
    property color accent: Theme.stateColor(sphereState)

    spacing: 14

    // Synchronise la couleur avec l'état courant.
    onSphereStateChanged: {
        accent = Theme.stateColor(sphereState)
    }

    // Transition douce lors d'un changement d'état.
    Behavior on accent {
        ColorAnimation {
            duration: Theme.animMedium
        }
    }

    Text {
        anchors.horizontalCenter: parent.horizontalCenter

        text: Theme.stateLabel(root.sphereState)

        color: root.accent

        font.family: Theme.fontFamily
        font.pixelSize: 15
        font.bold: true
        font.letterSpacing: 4
    }
}
