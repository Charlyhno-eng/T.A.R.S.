import QtQuick 2.15

Item {
    id: root
    required property var targetWindow

    // Only the outer edges receive input; controls inside remain interactive.
    Repeater {
        model: [Qt.LeftEdge, Qt.RightEdge, Qt.TopEdge, Qt.BottomEdge,
                Qt.LeftEdge | Qt.TopEdge, Qt.RightEdge | Qt.TopEdge,
                Qt.LeftEdge | Qt.BottomEdge, Qt.RightEdge | Qt.BottomEdge]

        MouseArea {
            required property int modelData
            readonly property bool leftEdge: (modelData & Qt.LeftEdge) !== 0
            readonly property bool rightEdge: (modelData & Qt.RightEdge) !== 0
            readonly property bool topEdge: (modelData & Qt.TopEdge) !== 0
            readonly property bool bottomEdge: (modelData & Qt.BottomEdge) !== 0
            readonly property bool corner: (leftEdge || rightEdge) && (topEdge || bottomEdge)

            width: corner ? 12 : (leftEdge || rightEdge ? 6 : root.width - 24)
            height: corner ? 12 : (topEdge || bottomEdge ? 6 : root.height - 24)
            x: leftEdge ? 0 : (rightEdge ? root.width - width : 12)
            y: topEdge ? 0 : (bottomEdge ? root.height - height : 12)
            cursorShape: corner
                ? (leftEdge === topEdge ? Qt.SizeFDiagCursor : Qt.SizeBDiagCursor)
                : (leftEdge || rightEdge ? Qt.SizeHorCursor : Qt.SizeVerCursor)
            onPressed: root.targetWindow.startSystemResize(modelData)
        }
    }
}
