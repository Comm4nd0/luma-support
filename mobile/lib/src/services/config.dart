// Override at build time with --dart-define=API_BASE=https://...
const String kApiBase = String.fromEnvironment(
  'API_BASE',
  defaultValue: 'http://10.0.2.2:8006/api/v1',
);
