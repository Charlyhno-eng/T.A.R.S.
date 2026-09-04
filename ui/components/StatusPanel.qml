import QtQuick 2.15
import theme 1.0

// Bandeau de statut : libellé d'état + petit visualiseur audio.
// Les barres s'animent uniquement pendant "listening" / "speaking".
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

    Row {
        anchors.horizontalCenter: parent.horizontalCenter

        spacing: 4
        height: 30

        Repeater {
            model: 22

            delegate: Rectangle {
                id: bar

                property real target: 0.15

                width: 3
                radius: 1.5

                color: root.accent

                height: Math.max(3, target * 26)

                anchors.bottom: parent.bottom

                // Animation de la hauteur des barres.
                Behavior on height {
                    NumberAnimation {
                        duration: 140
                        easing.type: Easing.OutQuad
                    }
                }

                Timer {
                    interval: 90 + Math.random() * 160

                    running: root.sphereState === "listening"
                             || root.sphereState === "speaking"

                    repeat: true

                    onTriggered: {
                        bar.target = 0.15 + Math.random() * 0.85
                    }
                }

                Behavior on target {
                    NumberAnimation {
                        duration: 200
                    }
                }
            }
        }
    }
}
