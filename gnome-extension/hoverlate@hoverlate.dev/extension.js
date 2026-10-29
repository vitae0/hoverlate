import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const SERVICE = 'org.hoverlate.Shell';
const OBJECT = '/org/hoverlate/Shell';
const XML = [
    '<node><interface name="org.hoverlate.Shell">',
    '<method name="GetPointer"><arg direction="out" type="i"/><arg direction="out" type="i"/></method>',
    '<method name="CaptureHover">',
    '<arg direction="out" type="i"/><arg direction="out" type="i"/>',
    '<arg direction="out" type="i"/><arg direction="out" type="i"/>',
    '<arg direction="out" type="i"/><arg direction="out" type="i"/>',
    '<arg direction="out" type="s"/></method>',
    '<method name="ShowTranslation"><arg direction="in" type="s"/><arg direction="in" type="s"/></method>',
    '<method name="HideTranslation"/>',
    '</interface></node>',
].join('');

class Bridge {
    constructor(extension) {
        this.extension = extension;
        this.lastCapture = 0;
        this.capturing = false;
    }

    GetPointer() {
        const [x, y] = global.get_pointer();
        return [x, y];
    }

    async CaptureHoverAsync(_params, invocation) {
        if (this.capturing) {
            invocation.return_dbus_error('org.hoverlate.Busy', 'Capture in progress');
            return;
        }
        const now = GLib.get_monotonic_time();
        if (now - this.lastCapture < 500000) {
            invocation.return_dbus_error('org.hoverlate.RateLimited', 'Try again shortly');
            return;
        }
        this.lastCapture = now;
        this.capturing = true;
        try {
            const [x, y] = global.get_pointer();
            const monitor = Main.layoutManager.monitors.find(m =>
                x >= m.x && x < m.x + m.width && y >= m.y && y < m.y + m.height);
            if (!monitor)
                throw new Error('Cursor is outside known monitors');
            const width = Math.min(520, monitor.width);
            const height = Math.min(220, monitor.height);
            const left = Math.min(Math.max(x - Math.floor(width / 2), monitor.x),
                monitor.x + monitor.width - width);
            const top = Math.min(Math.max(y - Math.floor(height / 2), monitor.y),
                monitor.y + monitor.height - height);
            const stream = Gio.MemoryOutputStream.new_resizable();
            const shooter = new Shell.Screenshot();
            await new Promise((resolve, reject) => {
                shooter.screenshot_area(left, top, width, height, stream, (obj, result) => {
                    try {
                        const [success] = obj.screenshot_area_finish(result);
                        if (!success)
                            reject(new Error('Screenshot refused'));
                        else
                            resolve();
                    } catch (error) {
                        reject(error);
                    }
                });
            });
            stream.close(null);
            const data = GLib.base64_encode(stream.steal_as_bytes().get_data());
            invocation.return_value(new GLib.Variant('(iiiiiis)',
                [x, y, left, top, width, height, data]));
        } catch (error) {
            invocation.return_dbus_error('org.hoverlate.CaptureFailed', String(error));
        } finally {
            this.capturing = false;
        }
    }

    ShowTranslation(word, translated) {
        this.extension.showTranslation(word, translated);
    }

    HideTranslation() {
        this.extension.hideTranslation();
    }
}

export default class HoverlateWaylandExtension extends Extension {
    enable() {
        this._label = new St.Label({
            text: '', visible: false, reactive: false,
            style: 'background-color: #181b22; color: #f8fafc; border: 1px solid #596171; border-radius: 9px; padding: 10px 14px; font-size: 14px; font-weight: bold;',
        });
        Main.layoutManager.addTopChrome(this._label);
        this._bridge = new Bridge(this);
        this._exported = Gio.DBusExportedObject.wrapJSObject(XML, this._bridge);
        this._owner = Gio.bus_own_name(
            Gio.BusType.SESSION, SERVICE, Gio.BusNameOwnerFlags.NONE,
            connection => {
                if (this._exported)
                    this._exported.export(connection, OBJECT);
            },
            () => {},
            () => {}
        );
    }

    showTranslation(word, translated) {
        if (!this._label)
            return;
        const w = String(word).replace(/\s+/g, ' ').slice(0, 80);
        const t = String(translated).replace(/\s+/g, ' ').slice(0, 150);
        this._label.set_text(w + '  →  ' + t);
        const [x, y] = global.get_pointer();
        const monitor = Main.layoutManager.monitors.find(m =>
            x >= m.x && x < m.x + m.width && y >= m.y && y < m.y + m.height);
        this._label.show();
        this._label.set_position(x + 18, y + 25);
        if (monitor) {
            const tw = this._label.get_width();
            const th = this._label.get_height();
            const px = Math.max(monitor.x, Math.min(x + 18, monitor.x + monitor.width - tw));
            const py = y + 25 + th > monitor.y + monitor.height
                ? Math.max(monitor.y, y - th - 18) : y + 25;
            this._label.set_position(px, py);
        }
    }

    hideTranslation() {
        this._label?.hide();
    }

    disable() {
        if (this._owner !== undefined) {
            Gio.bus_unown_name(this._owner);
            this._owner = undefined;
        }
        this._exported?.unexport();
        this._exported = null;
        this._bridge = null;
        if (this._label) {
            Main.layoutManager.removeChrome(this._label);
            this._label.destroy();
            this._label = null;
        }
    }
}
