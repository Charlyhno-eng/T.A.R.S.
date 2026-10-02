import QtQuick 2.15
import QtQuick.Controls 2.15
import theme 1.0

Rectangle {
    id: root
    property real textScale: 1
    readonly property bool english: assistant.language === "en"
    color: Qt.rgba(Theme.panelBackground.r, Theme.panelBackground.g, Theme.panelBackground.b, 0.78)
    radius: 18
    border.color: Theme.panelBorder

    Column {
        id: heading
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 24
        spacing: 8
        Text {
            text: "CONVERSATION"
            color: Theme.accentCyan
            font.family: Theme.fontFamily
            font.pixelSize: 12 * root.textScale
            font.bold: true
            font.letterSpacing: 2
        }
        Text {
            width: parent.width
            text: root.english ? "Your latest exchange" : "Votre dernier échange"
            color: Theme.textSecondary
            font.family: Theme.fontFamily
            font.pixelSize: 12 * root.textScale
            wrapMode: Text.WordWrap
        }
    }

    ScrollView {
        id: scroll
        objectName: "exchangeScroll"
        anchors.top: heading.bottom
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 24
        clip: true
        contentWidth: availableWidth
        Column {
            width: scroll.availableWidth
            spacing: 16
            Text {
                text: root.english ? "YOU" : "VOUS"
                color: Theme.accentMagenta
                font.pixelSize: 11 * root.textScale
                font.bold: true
                font.letterSpacing: 2
            }
            TextArea {
                width: parent.width
                text: assistant.transcript || (root.english
                    ? "Hold the robot to speak. Your words will appear here."
                    : "Maintenez le robot pour parler. Vos mots apparaîtront ici.")
                readOnly: true
                selectByMouse: true
                wrapMode: TextEdit.Wrap
                padding: 0
                background: null
                color: assistant.transcript ? Theme.textPrimary : Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: 15 * root.textScale
            }
            Rectangle { width: parent.width; height: 1; color: Theme.panelBorder }
            Text {
                text: "T.A.R.S."
                color: Theme.accentCyan
                font.pixelSize: 11 * root.textScale
                font.bold: true
                font.letterSpacing: 2
            }
            TextArea {
                width: parent.width
                text: assistant.response || (root.english
                    ? "The reply appears here as T.A.R.S. answers."
                    : "La réponse apparaît ici au fur et à mesure.")
                readOnly: true
                selectByMouse: true
                wrapMode: TextEdit.Wrap
                padding: 0
                background: null
                color: assistant.response ? Theme.textPrimary : Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: 15 * root.textScale
            }
        }
    }
}
