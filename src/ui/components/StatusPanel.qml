import QtQuick 2.15
import theme 1.0

Rectangle {
    id: root

    property string sphereState: "idle"
    property string language: "en"
    property color accent: Theme.stateColor(sphereState)
    property real textScale: 1
    property string label: Theme.stateLabel(sphereState, language)

    implicitWidth: statusRow.implicitWidth + 24
    implicitHeight: 34 * textScale
    radius: height / 2
    color: Qt.rgba(accent.r, accent.g, accent.b, 0.08)
    border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.22)

    Behavior on accent {
        ColorAnimation {
            duration: Theme.animMedium
        }
    }

    Row {
        id: statusRow
        anchors.centerIn: parent
        spacing: 8

        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: 6
            height: 6
            radius: 3
            color: root.accent
        }

        Text {
            text: root.label
            color: root.accent
            font.family: Theme.fontFamily
            font.pixelSize: 11 * root.textScale
            font.weight: Font.DemiBold
            font.letterSpacing: 0.8
        }
    }
}
