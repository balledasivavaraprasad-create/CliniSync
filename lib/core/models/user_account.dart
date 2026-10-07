class UserAccount {
  const UserAccount({
    required this.id,
    required this.email,
    required this.fullName,
    required this.role,
    required this.specialty,
    this.isActive = true,
    this.avatarUrl,
    this.token,
  });

  factory UserAccount.fromJson(Map<String, dynamic> json, {String? token}) {
    return UserAccount(
      id: json['id'] as String? ?? 'usr_001',
      email: json['email'] as String? ?? 'doctor@clinsync.health',
      fullName: json['full_name'] as String? ?? 'Dr. Willie Carter, MD',
      role: json['role'] as String? ?? 'doctor',
      specialty: json['specialty'] as String? ?? 'General Medicine',
      isActive: json['is_active'] as bool? ?? true,
      avatarUrl: json['avatar_url'] as String?,
      token: token ?? json['token'] as String?,
    );
  }

  final String id;
  final String email;
  final String fullName;
  final String role;
  final String specialty;
  final bool isActive;
  final String? avatarUrl;
  final String? token;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'id': id,
        'email': email,
        'full_name': fullName,
        'role': role,
        'specialty': specialty,
        'is_active': isActive,
        'avatar_url': avatarUrl,
        if (token != null) 'token': token,
      };

  static const UserAccount defaultDoctor = UserAccount(
    id: 'usr_doctor_001',
    email: 'doctor@clinsync.health',
    fullName: 'Dr. Willie Carter, MD',
    role: 'doctor',
    specialty: 'General Medicine',
  );
}
