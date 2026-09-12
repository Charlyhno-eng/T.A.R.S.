import QtQuick 2.15
import QtQuick.Controls 2.15
import theme 1.0

Item {
    id: root

    property string language: "fr"
    property bool selectorEnabled: true
    property bool expanded: false

    signal languageSelected(string language)

    width: 92
    height: 42
    z: 20

    Rectangle {
        id: trigger

        anchors.fill: parent

        radius: height / 2

        color: root.expanded || triggerMouse.containsMouse
            ? Qt.rgba(0.06, 0.14, 0.24, 0.96)
            : Qt.rgba(0.02, 0.06, 0.12, 0.50)

        border.width: 1
        border.color: root.expanded
            ? Theme.colorIdle
            : (triggerMouse.containsMouse
                ? Qt.rgba(Theme.colorIdle.r, Theme.colorIdle.g, Theme.colorIdle.b, 0.65)
                : Theme.panelBorder)

        Behavior on color {
            ColorAnimation { duration: Theme.animFast }
        }

        Behavior on border.color {
            ColorAnimation { duration: Theme.animFast }
        }

        Row {
            anchors.centerIn: parent

            spacing: 7

            Text {
                text: root.language === "en" ? "EN" : "FR"

                color: Theme.textPrimary

                font.family: Theme.fontFamily
                font.pixelSize: 13
                font.bold: true
                font.letterSpacing: 1.5
            }

            Text {
                text: root.expanded ? "⌃" : "⌄"

                color: Theme.textSecondary

                font.family: Theme.fontFamily
                font.pixelSize: 15
            }
        }

        MouseArea {
            id: triggerMouse

            anchors.fill: parent

            hoverEnabled: true
            enabled: root.selectorEnabled
            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor

            onClicked: root.expanded = !root.expanded
        }
    }

    Rectangle {
        id: menu

        anchors.top: parent.bottom
        anchors.right: parent.right
        anchors.topMargin: 8

        width: 140
        height: languageColumn.implicitHeight + 12

        visible: root.expanded

        radius: 12

        color: Qt.rgba(0.04, 0.10, 0.18, 0.98)

        border.width: 1
        border.color: Theme.panelBorder

        Column {
            id: languageColumn

            anchors {
                left: parent.left
                right: parent.right
                top: parent.top
                margins: 6
            }

            spacing: 2

            Repeater {
                model: [
                    { code: "fr", label: "Français" },
                    { code: "en", label: "English" }
                ]

                delegate: Rectangle {
                    id: option

                    required property var modelData

                    width: languageColumn.width
                    height: 34

                    radius: 8

                    color: optionMouse.containsMouse
                        ? Qt.rgba(
                            Theme.colorIdle.r,
                            Theme.colorIdle.g,
                            Theme.colorIdle.b,
                            0.15
                        )
                        : (root.language === modelData.code
                            ? Qt.rgba(Theme.colorIdle.r, Theme.colorIdle.g, Theme.colorIdle.b, 0.08)
                            : "transparent")

                    Row {
                        anchors {
                            left: parent.left
                            right: parent.right
                            verticalCenter: parent.verticalCenter
                            leftMargin: 11
                            rightMargin: 10
                        }

                        Text {
                            width: 98

                            text: modelData.label

                            color: root.language === modelData.code
                                ? Theme.colorIdle
                                : Theme.textPrimary

                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                        }

                        Text {
                            visible: root.language === modelData.code

                            text: "✓"

                            color: Theme.colorIdle

                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            font.bold: true
                        }
                    }

                    MouseArea {
                        id: optionMouse

                        anchors.fill: parent

                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor

                        onClicked: {
                            root.expanded = false
                            if (root.language !== option.modelData.code)
                                root.languageSelected(option.modelData.code)
                        }
                    }
                }
            }
        }
    }

    ToolTip.visible: triggerMouse.containsMouse && !root.expanded
    ToolTip.delay: 500
    ToolTip.text: root.language === "en"
        ? "Application and voice language"
        : "Langue de l'application et de la voix"
}
