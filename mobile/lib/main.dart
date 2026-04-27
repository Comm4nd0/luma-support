import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'src/services/auth_service.dart';
import 'src/services/api_client.dart';
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

class _Bootstrap extends StatelessWidget {
  const _Bootstrap();

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthService>();
    if (auth.loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    return auth.isAuthenticated ? const TicketListScreen() : const LoginScreen();
  }
}
