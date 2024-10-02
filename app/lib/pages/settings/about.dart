import 'package:flutter/material.dart';
import 'package:friend_private/pages/settings/webview.dart';
import 'package:friend_private/utils/analytics/intercom.dart';
import 'package:friend_private/utils/analytics/mixpanel.dart';
import 'package:friend_private/utils/other/temp.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:friend_private/services/translation_service.dart';

class AboutOmiPage extends StatefulWidget {
  const AboutOmiPage({super.key});

  @override
  State<AboutOmiPage> createState() => _AboutOmiPageState();
}

class _AboutOmiPageState extends State<AboutOmiPage> {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Theme.of(context).colorScheme.primary,
      appBar: AppBar(
        title:  Text(TranslationService.translate('About Omi')),
        backgroundColor: Theme.of(context).colorScheme.primary,
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            ListTile(
              contentPadding: const EdgeInsets.fromLTRB(4, 0, 24, 0),
              title:  Text(TranslationService.translate('Privacy Policy'), style: TextStyle(color: Colors.white)),
              trailing: const Icon(Icons.privacy_tip_outlined, size: 20),
              onTap: () {
                MixpanelManager().pageOpened('About Privacy Policy');
                routeToPage(
                  context,
                   PageWebView(url: 'https://www.omi.me/pages/privacy', title: TranslationService.translate('Privacy Policy')),
                );
              },
            ),
            ListTile(
              contentPadding: const EdgeInsets.fromLTRB(4, 0, 24, 0),
              title:  Text(TranslationService.translate('Visit Website'), style: TextStyle(color: Colors.white)),
              subtitle: const Text('https://omi.me'),
              trailing: const Icon(Icons.language_outlined, size: 20),
              onTap: () {
                MixpanelManager().pageOpened('About Visit Website');
                // routeToPage(context, const PageWebView(url: 'https://www.omi.me/', title: 'omi'));
                launchUrl(Uri.parse('https://www.omi.me/'));
              },
            ),
            ListTile(
              title:  Text(TranslationService.translate('Help or Inquiries?'), style: TextStyle(color: Colors.white)),
              subtitle: const Text('team@basedhardware.com'),
              contentPadding: const EdgeInsets.fromLTRB(4, 0, 24, 0),
              trailing: const Icon(Icons.help_outline_outlined, color: Colors.white, size: 20),
              onTap: () async {
                await IntercomManager.instance.intercom.displayMessenger();
              },
            ),
            ListTile(
              contentPadding: const EdgeInsets.fromLTRB(4, 0, 24, 0),
              title:  Text(TranslationService.translate('Join the community!'), style: TextStyle(color: Colors.white)),
              subtitle:  Text('2300+ ${TranslationService.translate('members and counting.')}'),
              trailing: const Icon(Icons.discord, color: Colors.purple, size: 20),
              onTap: () {
                MixpanelManager().pageOpened('About Join Discord');
                launchUrl(Uri.parse('https://discord.gg/ZutWMTJnwA'));
              },
            ),
          ],
        ),
      ),
    );
  }
}
