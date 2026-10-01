import QtQuick 2.15
import QtQuick.Controls 2.15
import theme 1.0
import "components"

ApplicationWindow {
    id: window

    width: 1000
    height: 700

    minimumWidth: 760
    minimumHeight: 560

    visible: true

    onClosing: function(close) {
        settingsDialog.close()
        if (desktop.hideToTray())
            close.accepted = false
    }

    title: "T.A.R.S. — Assistant"

    color: Theme.backgroundTop

    property string assistantState:
        assistant.state

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

    Canvas {
        anchors.fill: parent
        opacity: 0.045

        onPaint: {
            var ctx = getContext("2d")

            ctx.reset()

            ctx.strokeStyle =
                Theme.textPrimary

            ctx.lineWidth = 1

            var step = 48

            for (
                var x = 0;
                x < width;
                x += step
            ) {
                ctx.beginPath()
                ctx.moveTo(x, 0)
                ctx.lineTo(x, height)
                ctx.stroke()
            }

            for (
                var y = 0;
                y < height;
                y += step
            ) {
                ctx.beginPath()
                ctx.moveTo(0, y)
                ctx.lineTo(width, y)
                ctx.stroke()
            }
        }
    }

    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 122
        text: assistant.language === "en" ? "YOUR LOCAL VOICE ASSISTANT" :
                                             "VOTRE ASSISTANT VOCAL LOCAL"
        color: Theme.textSecondary
        font.family: Theme.fontFamily
        font.pixelSize: 11
        font.letterSpacing: 4
    }

    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 145
        text: assistant.language === "en" ? "How can I help?" : "Comment puis-je aider ?"
        color: Theme.textPrimary
        font.family: Theme.fontFamily
        font.pixelSize: 28
        font.weight: Font.DemiBold
    }

    TopBar {
        id: topBar

        anchors.top: parent.top
        anchors.left: parent.left

        anchors.margins: 24
    }

    Rectangle {
        id: downloadStatus

        anchors.top: modelDownloadButton.bottom
        anchors.right: parent.right

        anchors.topMargin: 10
        anchors.rightMargin: 24

        width: 300
        height: 42

        radius: 21

        color: Qt.rgba(
            0,
            0,
            0,
            0.18
        )

        border.width: 1

        border.color:
            Theme.panelBorder

        visible:
            assistant.modelsDownloading

        Text {
            anchors.centerIn: parent

            text:
                assistant.status

            color:
                Theme.textSecondary

            font.family:
                Theme.fontFamily

            font.pixelSize: 11

            font.letterSpacing: 1
        }
    }

    Rectangle {
        id: modelDownloadButton

        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: 20
        anchors.rightMargin: 24

        width: 42
        height: 42
        radius: 21
        color: downloadMouse.containsMouse ? Theme.panelBorder : "transparent"
        border.width: 1
        border.color: assistant.modelsDownloading
            ? Theme.colorListening : Theme.panelBorder

        Text {
            anchors.centerIn: parent
            text: assistant.modelsDownloading ? "..." :
                (assistant.modelsReady ? "✓" :
                    (assistant.modelsInstalled ? "…" : "↓"))
            color: assistant.modelsDownloading
                ? Theme.colorListening : Theme.textPrimary
            font.family: Theme.fontFamily
            font.pixelSize: assistant.modelsDownloading ? 14 : 22
            font.bold: true
        }

        MouseArea {
            id: downloadMouse
            anchors.fill: parent
            hoverEnabled: true
            enabled: !assistant.modelsDownloading && !assistant.modelsInstalled
            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked: assistant.downloadModels()
        }

        ToolTip.visible: downloadMouse.containsMouse
        ToolTip.delay: 500
        ToolTip.text: assistant.modelsReady
            ? (assistant.language === "en"
                ? "Pocket TTS and Parakeet are ready"
                : "Pocket TTS et Parakeet sont prêts")
            : (assistant.modelsInstalled
                ? (assistant.language === "en"
                    ? "Loading Pocket TTS and Parakeet"
                    : "Chargement de Pocket TTS et Parakeet")
                : (assistant.language === "en"
                    ? "Download Pocket TTS and Parakeet"
                    : "Télécharger Pocket TTS et Parakeet"))
    }

    Rectangle {
        id: settingsButton
        anchors.top: parent.top
        anchors.right: modelDownloadButton.left
        anchors.topMargin: 20
        anchors.rightMargin: 16
        width: 42
        height: 42
        radius: 21
        color: settingsMouse.containsMouse ? Theme.panelBorder : "transparent"
        border.width: 1
        border.color: Theme.panelBorder

        Text {
            anchors.centerIn: parent
            text: "⚙"
            color: Theme.textPrimary
            font.pixelSize: 25
        }
        MouseArea {
            id: settingsMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: settingsDialog.open()
        }
        ToolTip.visible: settingsMouse.containsMouse
        ToolTip.text: assistant.language === "en" ? "Settings" : "Paramètres"
    }

    SettingsDialog {
        id: settingsDialog
        anchors.centerIn: parent
    }

    Text {
        anchors.top: parent.top
        anchors.right: settingsButton.left

        anchors.topMargin: 33
        anchors.rightMargin: 16

        visible:
            !assistant.modelsDownloading

        text: Qt.formatDateTime(
            clock.now,
            "hh:mm:ss"
        )

        color:
            Theme.textSecondary

        font.family:
            Theme.fontFamily

        font.pixelSize: 13

        font.letterSpacing: 1

        QtObject {
            id: clock

            property date now:
                new Date()
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

    Item {
        id: centralItem

        anchors.centerIn: parent

        width: 360
        height: 360

        JarvisSphere {
            id: sphere

            anchors.centerIn: parent

            sphereState:
                window.assistantState

            animationsEnabled: window.active
            interactionEnabled: assistant.modelsReady && !assistant.modelsDownloading

            onPressed: assistant.startListening()
            onReleased: assistant.stopListening()
        }
    }

    Text {
        anchors.top:
            centralItem.bottom

        anchors.horizontalCenter:
            parent.horizontalCenter

        anchors.topMargin: 18

        text: {
            var english = assistant.language === "en"

            if (assistant.modelsDownloading)
                return assistant.status

            if (assistant.modelsLoading)
                return english
                    ? "LOADING LOCAL MODELS..."
                    : "CHARGEMENT DES MODÈLES LOCAUX..."

            if (!assistant.modelsInstalled)
                return english
                    ? "DOWNLOAD THE LOCAL MODELS TO BEGIN"
                    : "TÉLÉCHARGEZ LES MODÈLES LOCAUX POUR COMMENCER"

            if (!assistant.modelsReady)
                return assistant.status

            if (window.assistantState === "idle") {
                if (assistant.transcript)
                    return assistant.transcript
                return english
                    ? "HOLD T.A.R.S. TO SPEAK"
                    : "MAINTENEZ T.A.R.S. POUR PARLER"
            }

            if (window.assistantState === "speaking" && assistant.response)
                return "T.A.R.S.: " + assistant.response

            return assistant.status
        }

        color:
            Theme.textSecondary

        opacity: 0.8

        font.family:
            Theme.fontFamily

        font.pixelSize: 12

        font.letterSpacing: 1.2

        width: Math.min(parent.width - 80, 620)
        wrapMode: Text.WordWrap
        maximumLineCount: 3
        elide: Text.ElideRight

        horizontalAlignment:
            Text.AlignHCenter

        Behavior on opacity {
            NumberAnimation {
                duration: 400
            }
        }
    }

    Rectangle {
        anchors.horizontalCenter:
            parent.horizontalCenter

        anchors.bottom:
            statusPanel.top

        anchors.bottomMargin: 18

        width: 260
        height: 3

        radius: 1.5

        color:
            Theme.panelBorder

        visible:
            assistant.modelsDownloading

        Rectangle {
            id: loadingBar

            height: parent.height

            width:
                parent.width * 0.25

            radius:
                parent.radius

            color:
                Theme.colorListening

            SequentialAnimation on x {
                loops:
                    Animation.Infinite

                running:
                    assistant.modelsDownloading &&
                    window.active

                NumberAnimation {
                    from: 0

                    to:
                        loadingBar.parent.width -
                        loadingBar.width

                    duration: 1100

                    easing.type:
                        Easing.InOutQuad
                }

                NumberAnimation {
                    from:
                        loadingBar.parent.width -
                        loadingBar.width

                    to: 0

                    duration: 1100

                    easing.type:
                        Easing.InOutQuad
                }
            }
        }
    }

    StatusPanel {
        id: statusPanel

        anchors.bottom:
            parent.bottom

        anchors.horizontalCenter:
            parent.horizontalCenter

        anchors.bottomMargin: 40

        sphereState:
            window.assistantState

        language: assistant.language
    }

}
