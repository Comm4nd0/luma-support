import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'src/repositories/devices_repository.dart';
import 'src/repositories/me_repository.dart';
import 'src/services/api_client.dart';
import 'src/services/auth_service.dart';
import 'src/services/push_service.dart';
import 'src/screens/login_screen.dart';
import 'src/screens/ticket_list_screen.dart';
import 'src/theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await PushService.instance.initialize();
  runApp(const LumaSupportApp());
}

class LumaSupportApp extends StatelessWidget {
  const LumaSupportApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthService()),
        Provider(create: (ctx) => ApiClient(ctx.read<AuthService>())),
      ],
      child: MaterialApp(
        title: 'Luma Support',
        theme: lumaTheme,
        home: const _Bootstrap(),
        debugShowCheckedModeBanner: false,
      ),
    );
  }
}

class _Bootstrap extends StatefulWidget {
  const _Bootstrap();

  @override
  State<_Bootstrap> createState() => _BootstrapState();
}

class _BootstrapState extends State<_Bootstrap> {
  bool _devicesRegistered = false;

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthService>();
    if (auth.loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (auth.isAuthenticated) {
      // Register the device for push exactly once per authenticated session.
      // Pushed onto a post-frame callback so we don't kick off network work
      // mid-build, and fire-and-forget so the UI never blocks on it.
      if (!_devicesRegistered) {
        _devicesRegistered = true;
        final api = context.read<ApiClient>();
        WidgetsBinding.instance.addPostFrameCallback((_) async {
          try {
            await PushService.instance
                .registerWithBackend(DevicesRepository(api));
          } catch (e) {
            debugPrint('push register failed: $e');
          }
          try {
            await MeRepository(api).fetch();
          } catch (e) {
            debugPrint('me fetch failed: $e');
          }
        });
      }
      return const TicketListScreen();
    }
    _devicesRegistered = false;
    return const LoginScreen();
  }
}
