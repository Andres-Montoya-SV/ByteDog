#!/usr/bin/env swift
// Active WiFi scan via CoreWLAN (macOS). Outputs JSON array to stdout.
import CoreWLAN
import Foundation

guard let iface = CWWiFiClient.shared().interface() else {
    FileHandle.standardError.write(Data("no wifi interface\n".utf8))
    exit(1)
}

do {
    let networks = try iface.scanForNetworks(withSSID: nil)
    var rows: [[String: Any]] = []
    for net in networks {
        let ssid = net.ssid ?? "(hidden)"
        let bssid = net.bssid ?? ""
        let channel = net.wlanChannel?.channelNumber ?? 0
        let rssi = Int(net.rssiValue)
        rows.append([
            "ssid": ssid,
            "bssid": bssid,
            "channel": channel,
            "rssi": rssi,
        ])
    }
    let data = try JSONSerialization.data(withJSONObject: rows)
    FileHandle.standardOutput.write(data)
} catch {
    let msg = "{\"error\":\"\(error.localizedDescription)\"}"
    FileHandle.standardError.write(Data(msg.utf8))
    exit(1)
}
