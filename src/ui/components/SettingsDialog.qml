import QtQuick 2.15
import QtQuick.Controls 2.15
import theme 1.0

Dialog {
    id: root

    width: Math.min(parent.width - 48, 440)
    modal: true
    padding: 0
    standardButtons: Dialog.NoButton
    onOpened: {
        keyField.text = assistant.llmApiKey
        revealKey = false
    }

    background: Rectangle {
        radius: 18
        color: Theme.panelBackground
        border.width: 1
        border.color: Theme.panelBorder
    }

    Overlay.modal: Rectangle {
        color: Qt.rgba(0, 0, 0, 0.68)
    }

    contentItem: Column {
        spacing: 0

        Item {
            width: parent.width
            height: 76

            Rectangle {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.leftMargin: 24
                width: 42
                height: 2
                color: Theme.colorIdle
            }

            Text {
                anchors.left: parent.left
                anchors.leftMargin: 24
                anchors.verticalCenter: parent.verticalCenter
                text: assistant.language === "en" ? "SETTINGS" : "PARAMÈTRES"
                color: Theme.textPrimary
                font.family: Theme.fontFamily
                font.pixelSize: 19
                font.bold: true
                font.letterSpacing: 2
            }

            Rectangle {
                anchors.right: parent.right
                anchors.rightMargin: 20
                anchors.verticalCenter: parent.verticalCenter
                width: 30
                height: 30
                radius: 15
                color: closeMouse.containsMouse ? Theme.panelBorder : "transparent"
                Text {
                    anchors.centerIn: parent
                    text: "×"
                    color: Theme.textSecondary
                    font.pixelSize: 23
                }
                MouseArea {
                    id: closeMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.close()
                }
            }
        }

        Rectangle {
            width: parent.width
            height: 1
            color: Theme.panelBorder
        }

        Column {
            width: parent.width
            padding: 24
            spacing: 12

            Text {
                text: assistant.language === "en" ? "LANGUAGE" : "LANGUE"
                color: Theme.colorIdle
                font.family: Theme.fontFamily
                font.pixelSize: 11
                font.bold: true
                font.letterSpacing: 2
            }

            Text {
                text: assistant.language === "en"
                    ? "Application and voice language"
                    : "Langue de l'application et de la voix"
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: 12
            }

            Row {
                spacing: 10
                Repeater {
                    model: [
                        { code: "fr", label: "Français" },
                        { code: "en", label: "English" }
                    ]
                    delegate: Button {
                        required property var modelData
                        width: (root.width - 58) / 2
                        height: 42
                        enabled: !assistant.modelsDownloading && assistant.state === "idle"
                        text: modelData.label + (assistant.language === modelData.code ? "  ✓" : "")
                        onClicked: assistant.setLanguage(modelData.code)
                        contentItem: Text {
                            text: parent.text
                            color: parent.enabled
                                ? (assistant.language === parent.modelData.code ? Theme.colorIdle : Theme.textPrimary)
                                : Theme.textSecondary
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        background: Rectangle {
                            radius: 9
                            color: parent.down || parent.hovered
                                ? Qt.rgba(Theme.colorIdle.r, Theme.colorIdle.g, Theme.colorIdle.b, 0.16)
                                : Theme.backgroundTop
                            border.width: 1
                            border.color: assistant.language === parent.modelData.code
                                ? Theme.colorIdle : Theme.panelBorder
                        }
                    }
                }
            }

            Item { width: 1; height: 8 }

            Rectangle {
                width: parent.width - 48
                height: 1
                color: Theme.panelBorder
            }

            Item { width: 1; height: 8 }

            Text {
                text: "GLM 5.3 FLASH · Z.AI"
                color: Theme.colorIdle
                font.family: Theme.fontFamily
                font.pixelSize: 11
                font.bold: true
                font.letterSpacing: 2
            }

            Text {
                text: assistant.llmKeyConfigured
                    ? (assistant.language === "en" ? "API key saved on this device" : "Clé API enregistrée sur cet appareil")
                    : (assistant.language === "en" ? "No API key saved" : "Aucune clé API enregistrée")
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: 12
            }

            Item {
                id: keyEntry
                width: parent.width - 48
                height: 42
                property bool revealKey: false

                TextField {
                    id: keyField
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: parent.width - 36
                    leftPadding: 12
                    rightPadding: 8
                    echoMode: parent.revealKey ? TextInput.Normal : TextInput.Password
                    placeholderText: assistant.language === "en" ? "Enter API key" : "Saisir la clé API"
                    color: Theme.textPrimary
                    placeholderTextColor: Theme.textSecondary
                    font.family: Theme.fontFamily
                    selectByMouse: true
                    background: Rectangle {
                        radius: 9
                        color: Theme.backgroundTop
                        border.width: 1
                        border.color: keyField.activeFocus ? Theme.colorIdle : Theme.panelBorder
                    }
                }

                Button {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    width: 32
                    height: 36
                    padding: 0
                    Accessible.name: parent.revealKey
                        ? (assistant.language === "en" ? "Hide API key" : "Masquer la clé API")
                        : (assistant.language === "en" ? "Show API key" : "Afficher la clé API")
                    onClicked: parent.revealKey = !parent.revealKey
                    contentItem: Item {
                        Rectangle {
                            anchors.centerIn: parent
                            width: 18
                            height: 12
                            radius: 6
                            color: "transparent"
                            border.width: 1.5
                            border.color: Theme.textSecondary
                        }
                        Rectangle {
                            anchors.centerIn: parent
                            width: 5
                            height: 5
                            radius: 2.5
                            color: Theme.textSecondary
                        }
                        Rectangle {
                            anchors.centerIn: parent
                            width: 22
                            height: 1.5
                            rotation: -35
                            color: Theme.textSecondary
                            visible: !keyEntry.revealKey
                        }
                    }
                    background: Rectangle {
                        color: parent.hovered ? Theme.panelBorder : "transparent"
                        radius: 7
                    }
                }
            }

            Row {
                spacing: 10

                Button {
                    id: saveButton
                    width: 125
                    height: 40
                    text: assistant.language === "en" ? "Save key" : "Enregistrer"
                    enabled: keyField.text.trim().length > 0
                    onClicked: {
                        assistant.saveLlmApiKey(keyField.text)
                        keyField.text = ""
                        root.close()
                    }
                    contentItem: Text {
                        text: parent.text
                        color: parent.enabled ? Theme.backgroundTop : Theme.textSecondary
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: 9
                        color: parent.enabled ? Theme.colorIdle : Theme.panelBorder
                    }
                }

                Button {
                    height: 40
                    text: assistant.language === "en" ? "Remove key" : "Supprimer la clé"
                    enabled: assistant.llmKeyConfigured
                    onClicked: {
                        assistant.saveLlmApiKey("")
                        keyField.text = ""
                        root.close()
                    }
                    contentItem: Text {
                        text: parent.text
                        color: parent.enabled ? Theme.textPrimary : Theme.textSecondary
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        implicitWidth: 125
                        radius: 9
                        color: parent.hovered && parent.enabled ? Theme.panelBorder : "transparent"
                        border.width: 1
                        border.color: Theme.panelBorder
                    }
                }
            }
        }
    }
}
