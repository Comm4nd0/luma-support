enum UserRole { admin, engineer, client, unknown }

UserRole _roleFromString(String? v) {
  switch (v) {
    case 'admin':
      return UserRole.admin;
    case 'engineer':
      return UserRole.engineer;
    case 'client':
      return UserRole.client;
    default:
      return UserRole.unknown;
  }
}

/// Mirrors the DRF `UserSerializer` in accounts/serializers.py.
class AppUser {
  AppUser({
    required this.id,
    required this.email,
    required this.firstName,
    required this.lastName,
    required this.role,
    required this.phone,
    required this.clientId,
    required this.isStaff,
    required this.isActive,
  });

  final int id;
  final String email;
  final String firstName;
  final String lastName;
  final UserRole role;
  final String phone;
  final int? clientId;
  final bool isStaff;
  final bool isActive;

  bool get isClient => role == UserRole.client;
  bool get isEngineer => role == UserRole.engineer || role == UserRole.admin;
  bool get canViewAll => isStaff || isEngineer;
  String get displayName =>
      ('$firstName $lastName').trim().isEmpty ? email : '$firstName $lastName'.trim();

  factory AppUser.fromJson(Map<String, dynamic> json) => AppUser(
        id: json['id'] as int,
        email: json['email'] as String? ?? '',
        firstName: json['first_name'] as String? ?? '',
        lastName: json['last_name'] as String? ?? '',
        role: _roleFromString(json['role'] as String?),
        phone: json['phone'] as String? ?? '',
        clientId: json['client'] as int?,
        isStaff: json['is_staff'] as bool? ?? false,
        isActive: json['is_active'] as bool? ?? true,
      );
}
