import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:friend_private/backend/database/transcript_segment.dart';
import 'package:friend_private/backend/http/shared.dart';
import 'package:friend_private/backend/preferences.dart';
import 'package:friend_private/env/env.dart';
import 'package:friend_private/utils/ble/communication.dart';
import 'package:instabug_flutter/instabug_flutter.dart';
import 'package:web_socket_channel/io.dart';

enum WebsocketConnectionStatus { notConnected, connected, failed, closed, error }

String mapCodecToName(BleAudioCodec codec) {
  switch (codec) {
    case BleAudioCodec.opus:
      return 'opus';
    case BleAudioCodec.pcm16:
      return 'pcm16';
    case BleAudioCodec.pcm8:
      return 'pcm8';
    default:
      return 'pcm8';
  }
}

Future<IOWebSocketChannel?> _initWebsocketStream(
  void Function(List<TranscriptSegment>) onMessageReceived,
  VoidCallback onWebsocketConnectionSuccess,
  void Function(dynamic) onWebsocketConnectionFailed,
  void Function(int?, String?) onWebsocketConnectionClosed,
  void Function(dynamic) onWebsocketConnectionError,
  int sampleRate,
  String codec,
) async {
  debugPrint('Websocket Opening');
  final recordingsLanguage = SharedPreferencesUtil().recordingsLanguage;
  var params = '?language=$recordingsLanguage&sample_rate=$sampleRate&codec=$codec&uid=${SharedPreferencesUtil().uid}';

  IOWebSocketChannel channel = IOWebSocketChannel.connect(
    Uri.parse('${Env.apiBaseUrl!.replaceAll('https', 'wss')}listen$params'),
    // headers: {'Authorization': await getAuthHeader()},
  );

  await channel.ready.then((_) {
    channel.stream.listen(
      (event) {
        if (event == 'ping') return;
        final segments = jsonDecode(event);
        if (segments is List) {
          if (segments.isEmpty) return;
          onMessageReceived(segments.map((e) => TranscriptSegment.fromJson(e)).toList());
        } else {
          debugPrint(event.toString());
        }
      },
      onError: (err, stackTrace) {
        onWebsocketConnectionError(err); // error during connection
        CrashReporting.reportHandledCrash(err!, stackTrace, level: NonFatalExceptionLevel.warning);
      },
      onDone: (() {
        onWebsocketConnectionClosed(channel.closeCode, channel.closeReason);
      }),
      cancelOnError: true,
    );
  }).onError((err, stackTrace) {
    // no closing reason or code
    print(err);
    CrashReporting.reportHandledCrash(err!, stackTrace, level: NonFatalExceptionLevel.warning);
    onWebsocketConnectionFailed(err); // initial connection failed
  });

  try {
    await channel.ready;
    debugPrint('Websocket Opened');
    onWebsocketConnectionSuccess();
  } catch (err) {}
  return channel;
}

Future<IOWebSocketChannel?> streamingTranscript({
  required VoidCallback onWebsocketConnectionSuccess,
  required void Function(dynamic) onWebsocketConnectionFailed,
  required void Function(int?, String?) onWebsocketConnectionClosed,
  required void Function(dynamic) onWebsocketConnectionError,
  required void Function(List<TranscriptSegment>) onMessageReceived,
  required BleAudioCodec codec,
  required int sampleRate,
}) async {
  try {
    IOWebSocketChannel? channel = await _initWebsocketStream(
      onMessageReceived,
      onWebsocketConnectionSuccess,
      onWebsocketConnectionFailed,
      onWebsocketConnectionClosed,
      onWebsocketConnectionError,
      sampleRate,
      mapCodecToName(codec),
    );

    return channel;
  } catch (e) {
    debugPrint('Error receiving data: $e');
  } finally {}

  return null;
}

Future<void> handleBrilliantLabsFrameStream({
  required void Function(List<TranscriptSegment>) onMessageReceived,
  required void Function(List<int>) onAudioBytesReceived,
  required void Function(List<int>) onImageBytesReceived,
  required VoidCallback onWebsocketConnectionSuccess,
  required void Function(dynamic) onWebsocketConnectionFailed,
  required void Function(int?, String?) onWebsocketConnectionClosed,
  required void Function(dynamic) onWebsocketConnectionError,
  required BleAudioCodec codec,
  required int sampleRate,
}) async {
  IOWebSocketChannel? channel = await streamingTranscript(
    onWebsocketConnectionSuccess: onWebsocketConnectionSuccess,
    onWebsocketConnectionFailed: onWebsocketConnectionFailed,
    onWebsocketConnectionClosed: onWebsocketConnectionClosed,
    onWebsocketConnectionError: onWebsocketConnectionError,
    onMessageReceived: onMessageReceived,
    codec: codec,
    sampleRate: sampleRate,
  );

  if (channel != null) {
    await getBleAudioBytesListener(
      'brilliant_labs_frame_device_id',
      onAudioBytesReceived: onAudioBytesReceived,
    );

    await getBleImageBytesListener(
      'brilliant_labs_frame_device_id',
      onImageBytesReceived: onImageBytesReceived,
    );
  }
}
