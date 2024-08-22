import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:friend_private/devices/device.dart';
import 'package:friend_private/devices/deviceType.dart';
import 'package:friend_private/devices/friend/friendDevice.dart';

class FriendDeviceType extends BtleDeviceType {
  FriendDeviceType() : super();
  @override String get manufacturerName => "Based Hardware";
  @override String get deviceNameForMatching => "Friend";
  @override List<Guid> get serviceGuids => [friendServiceUuid.guid];
  @override Type get deviceType => FriendDevice;

  @override
  Device createDeviceFromScan(String name, String id, int? rssi) {
    FriendDevice device = FriendDevice(id);
    device.name = name;
    if (rssi != null) {
      device.rssi = rssi;
    }
    return device;
  } 
}