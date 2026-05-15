import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import 'src/repositories/devices_repository.dart';
import 'src/router.dart';
import 'src/services/api_client.dart';
import 'src/services/auth_service.dart';
import 'src/services/current_user.dart';
import 'src/services/push_router.dart';
import 'src/services/push_service.dart';
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
        ChangeNotifierProvider(create: (_) => CurrentUser()),
        Provider(create: (ctx) => ApiClient(ctx.read<AuthService>())),
      ],
      child: const _RouterRoot(),
    );
  }
}

/// Owns the [GoRouter] and reacts to auth state changes. The router is built
/// once and mutated via `refreshListenable`; rebuilding it would lose the
/// navigation stack.
class _RouterRoot extends StatefulWidget {
  const _RouterRoot();

  @override
  State<_RouterRoot> createState() => _RouterRootState();
}

class _RouterRootState extends State<_RouterRoot> {
  late final AuthService _auth;
  late final CurrentUser _currentUser;
  late final ApiClient _api;
  late final GoRouter _router;
  bool _sessionInitDone = false;

  @override
  void initState() {
    super.initState();
    _auth = context.read<AuthService>();
    _currentUser = context.read<CurrentUser>();
    _api = context.read<ApiClient>();
    _router = buildAppRouter(auth: _auth, currentUser: _currentUser);
    PushRouter.instance.attach(_router);
    _auth.addListener(_onAuthChanged);
    // First-load case: if a token was restored from secure storage we still
    // need to fetch /me to populate role + register the device.
    WidgetsBinding.instance.addPostFrameCallback((_) => _onAuthChanged());
  }

  @override
  void dispose() {
    _auth.removeListener(_onAuthChanged);
    super.dispose();
  }

  Future<void> _onAuthChanged() async {
    if (!_auth.isAuthenticated) {
      _sessionInitDone = false;
      _currentUser.clear();
      return;
    }
    if (_sessionInitDone) return;
    _sessionInitDone = true;
    try {
      await _currentUser.fetch(_api);
    } catch (e) {
      debugPrint('me fetch failed: $e');
    }
    try {
      await PushService.instance.registerWithBackend(DevicesRepository(_api));
    } catch (e) {
      debugPrint('push register failed: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'Luma Support',
      theme: lumaTheme,
      debugShowCheckedModeBanner: false,
      routerConfig: _router,
    );
  }
}
