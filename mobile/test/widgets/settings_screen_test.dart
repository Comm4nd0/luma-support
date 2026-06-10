import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:luma_support_mobile/src/screens/settings_screen.dart';
import 'package:luma_support_mobile/src/services/api_client.dart';
import 'package:luma_support_mobile/src/services/current_user.dart';
import 'package:luma_support_mobile/src/services/settings_service.dart';
import 'package:luma_support_mobile/src/theme.dart';

import '../helpers/fakes.dart';
import '../helpers/mock_dio.dart';

void main() {
  setUpAll(registerMockFallbacks);

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  Widget wrap(SettingsService settings) {
    final dio = MockDio();
    when(() => dio.patch<dynamic>(any(), data: any(named: 'data')))
        .thenAnswer((_) async => okResponse('/auth/users/me/', {}));
    return MultiProvider(
      providers: [
        ChangeNotifierProvider<SettingsService>.value(value: settings),
        Provider<ApiClient>.value(value: ApiClient.withDio(dio)),
        ChangeNotifierProvider<CurrentUser>.value(
            value: FakeCurrentUser(fakeEngineerUser())),
      ],
      child: MaterialApp(theme: lumaTheme, home: const SettingsScreen()),
    );
  }

  testWidgets('uses Cupertino switches and segmented theme control',
      (tester) async {
    final settings = SettingsService();
    await settings.load();
    await tester.pumpWidget(wrap(settings));
    await tester.pumpAndSettle();

    expect(find.byType(CupertinoSwitch), findsNWidgets(2));
    expect(find.byType(CupertinoSlidingSegmentedControl<ThemeMode>),
        findsOneWidget);
  });

  testWidgets('toggling the biometric switch updates SettingsService',
      (tester) async {
    final settings = SettingsService();
    await settings.load();
    await tester.pumpWidget(wrap(settings));
    await tester.pumpAndSettle();

    expect(settings.biometricRequired, isFalse);
    await tester.tap(find.byType(CupertinoSwitch).first);
    await tester.pumpAndSettle();
    expect(settings.biometricRequired, isTrue);
  });
}
