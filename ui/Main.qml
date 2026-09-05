import QtQuick 2.15
import QtQuick.Controls 2.15
import theme 1.0
import "components"

// Page unique de l'interface T.A.R.S.
//
// Python expose `ttsController` au contexte QML.
// Le clic sur la sphère déclenche alors directement le TTS.

ApplicationWindow {
    id: window

    width: 1000
    height: 700
    minimumWidth: 760
    minimumHeight: 560

    visible: true

    title: "T.A.R.S. — Assistant"

    color: Theme.backgroundTop

    property string assistantState: "idle"

    property string welcomeMessage: "Bonjour utilisateur, je suis votre assistant TARS, comment puis-je vous aider aujourd'hui ?"

    function cycleState() {
        if (assistantState === "idle") {
            assistantState = "listening"
        } else if (assistantState === "listening") {
            assistantState = "thinking"
        } else if (assistantState === "thinking") {
            assistantState = "speaking"
        } else {
            assistantState = "idle"
        }
    }

    function activateAssistant() {
        assistantState = "thinking"

        ttsController.speak(welcomeMessage)
    }

    Connections {
        target: ttsController

        function onSpeakingChanged(speaking) {
            if (speaking) {
                window.assistantState = "speaking"
            } else {
                window.assistantState = "idle"
            }
        }

        function onErrorOccurred(message) {
            console.error(
                "[T.A.R.S.][TTS] " + message
            )

            window.assistantState = "idle"
        }
    }

    // --- Fond ---
    Rectangle {
        anchors.fill: parent

        gradient: Gradient {
            GradientStop {
                position: 0.0
                color: Theme.backgroundTop
            }

            GradientStop {
                position: 1.0
                color: Theme.backgroundBottom
            }
        }
    }

    // --- Grille discrète façon HUD ---
    Canvas {
        anchors.fill: parent
        opacity: 0.06

        onPaint: {
            var ctx = getContext("2d")

            ctx.reset()

            ctx.strokeStyle = Theme.textPrimary
            ctx.lineWidth = 1

            var step = 40

            for (var x = 0; x < width; x += step) {
                ctx.beginPath()
                ctx.moveTo(x, 0)
                ctx.lineTo(x, height)
                ctx.stroke()
            }

            for (var y = 0; y < height; y += step) {
                ctx.beginPath()
                ctx.moveTo(0, y)
                ctx.lineTo(width, y)
                ctx.stroke()
            }
        }
    }

    // --- Bandeau supérieur ---
    TopBar {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.margins: 24
    }

    // --- Horloge en haut à droite ---
    Text {
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 24

        text: Qt.formatDateTime(
            clock.now,
            "hh:mm:ss"
        )

        color: Theme.textSecondary

        font.family: Theme.fontFamily
        font.pixelSize: 13
        font.letterSpacing: 1

        QtObject {
            id: clock

            property date now: new Date()
        }

        Timer {
            interval: 1000
            running: true
            repeat: true

            onTriggered: {
                clock.now = new Date()
            }
        }
    }

    // --- Sphère centrale + anneau de particules ---
    Item {
        id: centralItem

        anchors.centerIn: parent

        width: 380
        height: 380

        ParticleRing {
            anchors.centerIn: parent

            radius: 175

            particleColor:
                Theme.stateColor(
                    window.assistantState
                )
        }

        JarvisSphere {
            id: sphere

            anchors.centerIn: parent

            sphereState:
                window.assistantState

            onClicked: {
                window.activateAssistant()
            }
        }
    }

    // --- Indice discret ---
    Text {
        anchors.top: centralItem.bottom
        anchors.horizontalCenter: parent.horizontalCenter

        anchors.topMargin: 18

        text: "CLIQUEZ SUR LA SPHÈRE POUR INTERAGIR"

        color: Theme.textSecondary

        opacity:
            window.assistantState === "idle"
            ? 0.7
            : 0

        font.family: Theme.fontFamily
        font.pixelSize: 11
        font.letterSpacing: 2

        Behavior on opacity {
            NumberAnimation {
                duration: 400
            }
        }
    }

    // --- Bandeau de statut ---
    StatusPanel {
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter

        anchors.bottomMargin: 40

        sphereState:
            window.assistantState
    }
}
