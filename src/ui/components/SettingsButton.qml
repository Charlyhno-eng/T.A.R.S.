import QtQuick 2.15
import QtQuick.Controls 2.15
import theme 1.0

Button {
    id: root
    property bool primary: false
    implicitWidth: Math.max(110, contentItem.implicitWidth + 24)
    implicitHeight: 40
    contentItem: Text {
        text: root.text
        color: !root.enabled ? Theme.textSecondary
            : (root.primary ? Theme.backgroundTop : Theme.textPrimary)
        font.family: Theme.fontFamily
        font.pixelSize: 12
        font.bold: root.primary
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    background: Rectangle {
        radius: 9
        color: root.primary && root.enabled ? Theme.colorIdle
            : (root.hovered && root.enabled ? Theme.panelBorder : Theme.backgroundTop)
        border.width: 1
        border.color: root.primary && root.enabled ? Theme.colorIdle : Theme.panelBorder
    }
}
