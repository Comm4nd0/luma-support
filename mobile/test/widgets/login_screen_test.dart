import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:luma_support_mobile/src/screens/login_screen.dart';
import 'package:luma_support_mobile/src/services/auth_service.dart';

import '../helpers/fakes.dart';

Widget _wrap(Widget child, FakeAuthService auth) {
  return MaterialApp(
    home: ChangeNotifierProvider<AuthService>.value(
      value: auth,
      child: child,
    ),
  );
}

void main() {
  testWidgets('renders the email + password fields and Sign in button',
      (tester) async {
    final auth = FakeAuthService();
    await tester.pumpWidget(_wrap(const LoginScreen(), auth));
    expect(find.byType(TextField), findsNWidgets(2));
    expect(find.widgetWithText(ElevatedButton, 'Sign in'), findsOneWidget);
  });

  testWidgets('tapping Sign in calls auth.login', (tester) async {
    final auth = FakeAuthService();
    await tester.pumpWidget(_wrap(const LoginScreen(), auth));
    await tester.enterText(find.byType(TextField).first, 'marco@example.com');
    await tester.enterText(find.byType(TextField).last, 'hunter2');
    await tester.tap(find.widgetWithText(ElevatedButton, 'Sign in'));
    await tester.pumpAndSettle();
    expect(auth.isAuthenticated, true);
  });

  testWidgets('shows TOTP step when backend asks for it', (tester) async {
    final auth = FakeAuthService(totpRequired: true, expectedTotpCode: '123456');
    await tester.pumpWidget(_wrap(const LoginScreen(), auth));
    await tester.enterText(find.byType(TextField).first, 'eng@luma.test');
    await tester.enterText(find.byType(TextField).last, 'goodpass');
    await tester.tap(find.widgetWithText(ElevatedButton, 'Sign in'));
    await tester.pumpAndSettle();

    expect(find.text('Two-factor verification'), findsOneWidget);
    expect(auth.isAuthenticated, false);

    await tester.enterText(find.byType(TextField).last, '123456');
    await tester.tap(find.widgetWithText(ElevatedButton, 'Verify'));
    await tester.pumpAndSettle();
    expect(auth.isAuthenticated, true);
  });

  testWidgets('rejects wrong TOTP and keeps user on the verify step',
      (tester) async {
    final auth = FakeAuthService(totpRequired: true, expectedTotpCode: '123456');
    await tester.pumpWidget(_wrap(const LoginScreen(), auth));
    await tester.enterText(find.byType(TextField).first, 'eng@luma.test');
    await tester.enterText(find.byType(TextField).last, 'goodpass');
    await tester.tap(find.widgetWithText(ElevatedButton, 'Sign in'));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).last, '000000');
    await tester.tap(find.widgetWithText(ElevatedButton, 'Verify'));
    await tester.pumpAndSettle();
    expect(find.text('Invalid two-factor code.'), findsOneWidget);
    expect(auth.isAuthenticated, false);
  });
}
