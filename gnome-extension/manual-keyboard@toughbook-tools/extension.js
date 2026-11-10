import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

export default class ManualKeyboardExtension extends Extension {
    enable() {
        const manager = Main.keyboard;
        this._manager = manager;
        this._original = manager._lastDeviceIsTouchscreen;
        manager._lastDeviceIsTouchscreen = () => false;
        manager._syncEnabled();
    }

    disable() {
        if (!this._manager)
            return;
        this._manager._lastDeviceIsTouchscreen = this._original;
        this._manager._syncEnabled();
        this._manager = null;
        this._original = null;
    }
}
