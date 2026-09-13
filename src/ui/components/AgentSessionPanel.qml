import QtQuick 2.15
import theme 1.0

Rectangle {
    id: root

    property string activeAgent: ""
    property string language: "en"

    width: sessionLabel.implicitWidth + 32
    height: 32
    radius: height / 2
    color: Qt.rgba(
        Theme.colorListening.r,
        Theme.colorListening.g,
        Theme.colorListening.b,
        0.12
    )
    border.width: 1
    border.color: Qt.rgba(
        Theme.colorListening.r,
        Theme.colorListening.g,
        Theme.colorListening.b,
        0.65
    )
    visible: activeAgent.length > 0

    Text {
        id: sessionLabel

        anchors.centerIn: parent

        text: root.language === "en"
            ? "CONNECTED TO " + root.activeAgent.toUpperCase()
            : "CONNECTÉ À " + root.activeAgent.toUpperCase()

        color: Theme.colorListening
        font.family: Theme.fontFamily
        font.pixelSize: 11
        font.bold: true
        font.letterSpacing: 1.5
    }
}
