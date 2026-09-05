import QtQuick 2.15
import QtQuick.Controls 2.15
import QtMultimedia 6.5
import theme 1.0
import "components"

ApplicationWindow {
    id: window

    width: 1000
    height: 700

    minimumWidth: 760
    minimumHeight: 560

    visible: true

    title: "T.A.R.S. — Assistant"

    color: Theme.backgroundTop

    // ---------------------------------------------------------------
    // État
    // ---------------------------------------------------------------

    property string assistantState: assistant.state

    // ---------------------------------------------------------------
    // Lecture audio
    // ---------------------------------------------------------------

    AudioOutput {
        id: audioOutput

        volume: 1.0
    }

    MediaPlayer {
        id: audioPlayer

        audioOutput: audioOutput

        onPlaybackStateChanged: {
            if (playbackState === MediaPlayer.PlayingState) {
                console.log(
                    "[T.A.R.S.][Audio] Lecture de la réponse."
                )
            }
        }

        /*
         * C'est cet événement qui détermine la véritable fin de la
         * réponse vocale.
         *
         * EndOfMedia signifie que le fichier audio vient d'être lu
         * jusqu'à sa dernière milliseconde.
         */
        onMediaStatusChanged: {
            if (mediaStatus === MediaPlayer.EndOfMedia) {
                console.log(
                    "[T.A.R.S.][Audio] Fin réelle de la réponse."
                )

                assistant.audioPlaybackFinished()
            }
        }

        onErrorOccurred: {
            if (error !== MediaPlayer.NoError) {
                console.error(
                    "[T.A.R.S.][Audio] Erreur :",
                    errorString
                )

                assistant.audioPlaybackFinished()
            }
        }
    }

    Connections {
        target: assistant

        function onAudioPathChanged() {
            if (!assistant.audioPath)
                return

            /*
             * Arrêt manuel d'une éventuelle ancienne lecture.
             *
             * Important :
             * EndOfMedia n'est pas utilisé ici, car il s'agit d'un
             * arrêt volontaire et non de la fin naturelle de la phrase.
             */
            audioPlayer.stop()

            audioPlayer.source =
                "file://" + assistant.audioPath

            audioPlayer.play()
        }
    }

    // ---------------------------------------------------------------
    // Fond
    // ---------------------------------------------------------------

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

    // ---------------------------------------------------------------
    // Grille HUD
    // ---------------------------------------------------------------

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

    // ---------------------------------------------------------------
    // Bandeau supérieur
    // ---------------------------------------------------------------

    TopBar {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.margins: 24
    }

    // ---------------------------------------------------------------
    // Horloge
    // ---------------------------------------------------------------

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

    // ---------------------------------------------------------------
    // Sphère centrale
    // ---------------------------------------------------------------

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
                assistant.activate()
            }
        }
    }

    // ---------------------------------------------------------------
    // Message utilisateur / statut
    // ---------------------------------------------------------------

    Text {
        anchors.top: centralItem.bottom
        anchors.horizontalCenter: parent.horizontalCenter

        anchors.topMargin: 18

        text: {
            if (assistant.ttsLoading)
                return assistant.status

            if (!assistant.ttsReady)
                return assistant.status

            if (window.assistantState === "idle")
                return "CLIQUEZ SUR LA SPHÈRE POUR INTERAGIR"

            return assistant.status
        }

        color: Theme.textSecondary

        opacity: 0.8

        font.family: Theme.fontFamily
        font.pixelSize: 11
        font.letterSpacing: 2

        Behavior on opacity {
            NumberAnimation {
                duration: 400
            }
        }
    }

    // ---------------------------------------------------------------
    // Indicateur de chargement TTS
    // ---------------------------------------------------------------

    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter

        anchors.bottom: statusPanel.top
        anchors.bottomMargin: 18

        width: 260
        height: 3

        radius: 1.5

        color: Theme.panelBorder

        visible: assistant.ttsLoading

        Rectangle {
            id: loadingBar

            height: parent.height
            width: parent.width * 0.25

            radius: parent.radius

            color: Theme.colorListening

            SequentialAnimation on x {
                loops: Animation.Infinite

                NumberAnimation {
                    from: 0

                    to:
                        loadingBar.parent.width -
                        loadingBar.width

                    duration: 1100

                    easing.type: Easing.InOutQuad
                }

                NumberAnimation {
                    from:
                        loadingBar.parent.width -
                        loadingBar.width

                    to: 0

                    duration: 1100

                    easing.type: Easing.InOutQuad
                }
            }
        }
    }

    // ---------------------------------------------------------------
    // Bandeau de statut
    // ---------------------------------------------------------------

    StatusPanel {
        id: statusPanel

        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter

        anchors.bottomMargin: 40

        sphereState:
            window.assistantState
    }
}
