// the chamesle sign-in screen: a lock screen with the clock first, any key or click slides it up to sign in,
// like windows does it. sddm hands us userModel, sessionModel, sddm (login, power) and config (theme.conf)
import QtQuick
import QtQuick.Controls

Rectangle {
    id: root
    width: 1920
    height: 1080
    color: "#246070"

    readonly property string fontName: config.font || "Inter"
    // everything is drawn for 1080p and scaled to the screen
    readonly property real s: Math.min(width / 1920, height / 1080)
    // preview=signin in theme.conf starts on the sign-in box, for screenshots of it
    property bool locked: config.preview !== "signin"
    property int userIndex: userModel.lastIndex >= 0 ? userModel.lastIndex : 0
    property int sessionIndex: sessionModel.lastIndex >= 0 ? sessionModel.lastIndex : 0
    property string error: ""

    // the users, read through a repeater: sddm's model only gives its roles to delegates
    Repeater {
        id: users
        model: userModel
        delegate: Item {
            property string login: model.name
            property string realName: model.realName
            property string icon: model.icon
            property bool needsPassword: model.needsPassword
        }
    }
    readonly property var user: users.count > 0 ? users.itemAt(Math.min(userIndex, users.count - 1)) : null
    readonly property string userName: user ? user.login : ""
    readonly property string shownName: user ? (user.realName || user.login) : ""

    function unlock() {
        if (!locked) return
        locked = false
        password.forceActiveFocus()
    }
    function signIn() {
        if (busy.running) return
        error = ""
        busy.running = true
        sddm.login(userName, password.text, sessionIndex)
    }

    Connections {
        target: sddm
        function onLoginFailed() {
            busy.running = false
            password.text = ""
            error = "That password isn't right. Try again."
            shake.restart()
            password.forceActiveFocus()
        }
        function onLoginSucceeded() { busy.running = false }
    }

    Image {
        anchors.fill: parent
        source: config.background || "assets/background.jpg"
        fillMode: Image.PreserveAspectCrop
        asynchronous: false
    }

    // dark at the top and bottom so the white clock and labels read on bright photos
    Rectangle {
        anchors.top: parent.top
        width: parent.width
        height: parent.height * 0.42
        gradient: Gradient {
            GradientStop { position: 0; color: "#66000000" }
            GradientStop { position: 1; color: "#00000000" }
        }
    }
    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width
        height: parent.height * 0.2
        gradient: Gradient {
            GradientStop { position: 0; color: "#00000000" }
            GradientStop { position: 1; color: "#73000000" }
        }
    }

    // ---- the lock screen ----
    Item {
        id: lock
        width: parent.width
        height: parent.height
        y: root.locked ? 0 : -parent.height * 0.12
        opacity: root.locked ? 1 : 0
        visible: opacity > 0
        Behavior on y { NumberAnimation { duration: 350; easing.type: Easing.OutCubic } }
        Behavior on opacity { NumberAnimation { duration: 250 } }

        Text {
            id: time
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height * 0.11
            color: "white"
            font.family: root.fontName
            font.pixelSize: 132 * root.s
            font.weight: Font.DemiBold
            text: Qt.formatTime(clock.now, config.clock === "12" ? "h:mm" : "HH:mm")
            style: Text.Raised
            styleColor: "#30000000"
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: time.bottom
            anchors.topMargin: 2 * root.s
            color: "white"
            font.family: root.fontName
            font.pixelSize: 26 * root.s
            font.weight: Font.Medium
            text: Qt.formatDate(clock.now, "dddd, d MMMM")
        }
    }
    Timer {
        id: clock
        property date now: new Date()
        interval: 1000
        running: true
        repeat: true
        onTriggered: now = new Date()
    }

    // ---- signing in ----
    Item {
        id: signin
        anchors.fill: parent
        opacity: root.locked ? 0 : 1
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 200 } }

        // a grey panel with a black title bar, like a NeXT login window
        Rectangle {
            id: pane
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            width: 560 * root.s
            height: title.height + box.implicitHeight + 56 * root.s
            color: "black"
            // the shadow it throws on the wallpaper, hard edged
            Rectangle {
                z: -1
                x: 8 * root.s; y: 8 * root.s
                width: parent.width; height: parent.height
                color: "#60000000"
            }
            Bevel {
                anchors.fill: parent
                anchors.margins: 1
            }
            Rectangle {
                id: title
                x: 1; y: 1
                width: parent.width - 2
                height: 30 * root.s
                color: "black"
                Text {
                    anchors.centerIn: parent
                    text: "Sign in to " + (sddm.hostName || "Chamesle")
                    color: "white"
                    font.family: root.fontName
                    font.pixelSize: 15 * root.s
                    font.weight: Font.DemiBold
                }
            }
            Rectangle { x: 1; y: title.height + 1; width: parent.width - 2; height: 1; color: "#555555" }

            Row {
                id: box
                x: 28 * root.s
                anchors.top: title.bottom
                anchors.topMargin: 28 * root.s
                spacing: 24 * root.s

                // the picture people set, or the plain one, sunk into the panel
                Bevel {
                    width: 112 * root.s
                    height: width
                    sunk: true
                    face: "#ffffff"
                    Image {
                        id: face
                        anchors.fill: parent
                        anchors.margins: 3 * root.s
                        source: root.user && root.user.icon ? root.user.icon : "assets/user.svg"
                        sourceSize: Qt.size(width * 2, height * 2)
                        fillMode: Image.PreserveAspectCrop
                        onStatusChanged: if (status === Image.Error) source = "assets/user.svg"
                    }
                }

                Column {
                    spacing: 12 * root.s
                    width: pane.width - 112 * root.s - 80 * root.s

                    Text {
                        color: "black"
                        font.family: root.fontName
                        font.pixelSize: 24 * root.s
                        font.weight: Font.DemiBold
                        text: root.shownName
                        elide: Text.ElideRight
                        width: parent.width
                    }

                    // the password box, sunk in, with a button that has the arrow on it
                    Item {
                        id: field
                        width: parent.width
                        height: 34 * root.s
                        visible: !root.user || root.user.needsPassword
                        property real shakeX: 0
                        transform: Translate { x: field.shakeX }
                        SequentialAnimation {
                            id: shake
                            NumberAnimation { target: field; property: "shakeX"; to: -12 * root.s; duration: 50 }
                            NumberAnimation { target: field; property: "shakeX"; to: 12 * root.s; duration: 70 }
                            NumberAnimation { target: field; property: "shakeX"; to: -6 * root.s; duration: 60 }
                            NumberAnimation { target: field; property: "shakeX"; to: 0; duration: 50 }
                        }
                        Bevel {
                            id: well
                            anchors.left: parent.left
                            anchors.right: go.left
                            anchors.rightMargin: 8 * root.s
                            height: parent.height
                            sunk: true
                            face: "#ffffff"
                        }
                        TextInput {
                            id: password
                            anchors.left: well.left
                            anchors.right: reveal.left
                            anchors.leftMargin: 10 * root.s
                            anchors.verticalCenter: parent.verticalCenter
                            color: "black"
                            font.family: root.fontName
                            font.pixelSize: 17 * root.s
                            echoMode: reveal.pressed ? TextInput.Normal : TextInput.Password
                            passwordCharacter: "•"
                            clip: true
                            selectByMouse: true
                            selectionColor: "#246070"
                            onAccepted: root.signIn()
                            onTextChanged: if (text.length) root.error = ""
                            Keys.onEscapePressed: { text = ""; root.locked = true }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Password"
                                color: "#888888"
                                font: password.font
                                visible: !password.text && !password.preeditText
                            }
                        }
                        MouseArea {
                            id: reveal
                            anchors.right: well.right
                            anchors.verticalCenter: parent.verticalCenter
                            width: 32 * root.s
                            height: parent.height
                            visible: password.text.length > 0
                            Image {
                                anchors.centerIn: parent
                                source: "assets/eye-dark.svg"
                                width: 18 * root.s
                                height: width
                                sourceSize: Qt.size(width * 2, height * 2)
                                opacity: reveal.pressed ? 1 : 0.6
                            }
                        }
                        MouseArea {
                            id: go
                            anchors.right: parent.right
                            width: 46 * root.s
                            height: parent.height
                            onClicked: root.signIn()
                            Bevel { anchors.fill: parent; sunk: go.pressed }
                            Image {
                                anchors.centerIn: parent
                                anchors.horizontalCenterOffset: go.pressed ? 1 : 0
                                anchors.verticalCenterOffset: go.pressed ? 1 : 0
                                source: "assets/arrow-dark.svg"
                                width: 20 * root.s
                                height: width
                                sourceSize: Qt.size(width * 2, height * 2)
                                visible: !busy.running
                            }
                            BusyIndicator {
                                id: busy
                                anchors.centerIn: parent
                                width: 22 * root.s
                                height: width
                                running: false
                                visible: running
                            }
                        }
                    }

                    // no password on this account (autologin users): just a button
                    MouseArea {
                        id: plain
                        visible: root.user && !root.user.needsPassword
                        width: 140 * root.s
                        height: 34 * root.s
                        onClicked: root.signIn()
                        Bevel { anchors.fill: parent; sunk: plain.pressed }
                        Text {
                            anchors.centerIn: parent
                            text: "Sign in"
                            color: "black"
                            font.family: root.fontName
                            font.pixelSize: 16 * root.s
                        }
                    }

                    Text {
                        color: "#800000"
                        font.family: root.fontName
                        font.pixelSize: 14 * root.s
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: root.error || (keyboard.capsLock ? "Caps Lock is on" : " ")
                    }
                }
            }
        }

        // other people on this computer, bottom left
        Column {
            anchors.left: parent.left
            anchors.bottom: parent.bottom
            anchors.margins: 28 * root.s
            spacing: 4 * root.s
            visible: users.count > 1
            Repeater {
                model: userModel
                delegate: Rectangle {
                    width: 260 * root.s
                    height: 52 * root.s
                    radius: 6 * root.s
                    color: index === root.userIndex ? "#38ffffff" : (pick.containsMouse ? "#20ffffff" : "transparent")
                    Row {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: 10 * root.s
                        spacing: 12 * root.s
                        Canvas {
                            width: 34 * root.s
                            height: width
                            property string img: model.icon || "assets/user.svg"
                            Component.onCompleted: loadImage(img)
                            onImageLoaded: requestPaint()
                            onPaint: {
                                var c = getContext("2d")
                                c.reset(); c.beginPath()
                                c.arc(width / 2, height / 2, width / 2, 0, 2 * Math.PI)
                                c.closePath(); c.clip()
                                if (isImageLoaded(img)) c.drawImage(img, 0, 0, width, height)
                                else { c.fillStyle = "#e6e9ee"; c.fill() }
                            }
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: model.realName || model.name
                            color: "white"
                            font.family: root.fontName
                            font.pixelSize: 16 * root.s
                        }
                    }
                    MouseArea {
                        id: pick
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: { root.userIndex = index; password.text = ""; root.error = ""; password.forceActiveFocus() }
                    }
                }
            }
        }
    }

    Row {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 30 * root.s
        spacing: 12 * root.s
        Image {
            anchors.verticalCenter: parent.verticalCenter
            source: "assets/logo.png"
            width: 34 * root.s
            height: width
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: "Chamesle"
            color: "white"
            font.family: root.fontName
            font.pixelSize: 26 * root.s
            font.weight: Font.DemiBold
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: config.version || ""
            color: "#d9ffffff"
            font.family: root.fontName
            font.pixelSize: 20 * root.s
        }
    }

    // bottom right on both screens: which desktop, and power
    Row {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 24 * root.s
        spacing: 6 * root.s

        Repeater {
            id: sessions
            model: sessionModel
            delegate: Item { property string label: model.name }
        }
        Corner {
            visible: sessions.count > 1
            icon: "assets/desktop.svg"
            label: sessions.count ? sessions.itemAt(Math.min(root.sessionIndex, sessions.count - 1)).label : ""
            onClicked: sessionMenu.open()
            Menu {
                id: sessionMenu
                y: -height - 8
                Repeater {
                    model: sessionModel
                    MenuItem {
                        text: model.name
                        checkable: true
                        checked: index === root.sessionIndex
                        onTriggered: root.sessionIndex = index
                    }
                }
            }
        }
        Corner {
            icon: "assets/power.svg"
            red: true
            onClicked: powerMenu.open()
            Menu {
                id: powerMenu
                y: -height - 8
                MenuItem { text: "Sleep"; enabled: sddm.canSuspend; onTriggered: sddm.suspend() }
                MenuItem { text: "Shut down"; enabled: sddm.canPowerOff; onTriggered: sddm.powerOff() }
                MenuItem { text: "Restart"; enabled: sddm.canReboot; onTriggered: sddm.reboot() }
            }
        }
    }

    component Corner: MouseArea {
        id: corner
        property string icon
        property string label: ""
        property bool red: false
        width: label ? labelText.implicitWidth + 56 * root.s : 44 * root.s
        height: 40 * root.s
        Rectangle {
            anchors.fill: parent
            color: "black"
            Bevel { anchors.fill: parent; anchors.margins: 1; sunk: corner.pressed }
        }
        Row {
            anchors.centerIn: parent
            spacing: 8 * root.s
            Image {
                anchors.verticalCenter: parent.verticalCenter
                // the black copy of the icon, for the grey button
                source: corner.icon.replace(".svg", "-dark.svg")
                width: 22 * root.s
                height: width
                sourceSize: Qt.size(width * 2, height * 2)
            }
            Text {
                id: labelText
                anchors.verticalCenter: parent.verticalCenter
                visible: corner.label !== ""
                text: corner.label
                color: "black"
                font.family: root.fontName
                font.pixelSize: 15 * root.s
            }
        }
    }

    // grey with a light top-left edge and a dark bottom-right one, or the other way round when sunk in
    component Bevel: Item {
        property bool sunk: false
        property color face: "#aaaaaa"
        readonly property int b: Math.max(1, Math.round(2 * root.s))
        Rectangle { anchors.fill: parent; color: sunk ? "#ffffff" : "#555555" }
        Rectangle { width: parent.width - b; height: parent.height - b; color: sunk ? "#555555" : "#ffffff" }
        Rectangle { x: b; y: b; width: parent.width - 2 * b; height: parent.height - 2 * b; color: face }
    }

    // the lock screen goes on any key or click
    MouseArea {
        anchors.fill: parent
        enabled: root.locked
        visible: root.locked
        onClicked: root.unlock()
    }
    focus: true
    Keys.onPressed: function (event) {
        if (root.locked) {
            root.unlock()
            // the first letter typed goes into the password, like windows
            if (event.text && event.text.trim() !== "" && event.key !== Qt.Key_Space) password.insert(0, event.text)
            event.accepted = true
        }
    }
    Component.onCompleted: locked ? forceActiveFocus() : password.forceActiveFocus()
}
