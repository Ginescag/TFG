import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shadcn_ui/shadcn_ui.dart';

import '../../data/api_exception.dart';
import '../../models/user.dart';
import '../../providers.dart';
import '../../widgets/app_drawer.dart';
import '../../widgets/error_view.dart';
import '../../widgets/loading_view.dart';

final profileProvider = FutureProvider<User>((ref) {
  return ref.read(userRepositoryProvider).getProfile();
});

class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _phoneController = TextEditingController();
  final _passwordController = TextEditingController();

  final _oldPasswordController = TextEditingController();
  final _newPasswordController = TextEditingController();

  bool _updating = false;

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    _passwordController.dispose();
    _oldPasswordController.dispose();
    _newPasswordController.dispose();
    super.dispose();
  }

  Future<void> _updateInfo() async {
    setState(() => _updating = true);
    try {
      await ref
          .read(userRepositoryProvider)
          .updateInfo(
            nombre: _nameController.text.trim(),
            email: _emailController.text.trim(),
            password: _passwordController.text.trim(),
            tlf: _phoneController.text.trim().isEmpty
                ? null
                : _phoneController.text.trim(),
          );
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Profile updated')));
        ref.refresh(profileProvider);
      }
    } on ApiException catch (e) {
      _showError(e.message);
    } catch (_) {
      _showError('Failed to update the profile.');
    } finally {
      if (mounted) setState(() => _updating = false);
    }
  }

  Future<void> _updatePassword() async {
    setState(() => _updating = true);
    try {
      await ref
          .read(userRepositoryProvider)
          .updatePassword(
            oldPassword: _oldPasswordController.text.trim(),
            newPassword: _newPasswordController.text.trim(),
          );
      if (mounted) {
        _oldPasswordController.clear();
        _newPasswordController.clear();
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Password updated')));
      }
    } on ApiException catch (e) {
      _showError(e.message);
    } catch (_) {
      _showError('Failed to update the password.');
    } finally {
      if (mounted) setState(() => _updating = false);
    }
  }

  void _showError(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final profileAsync = ref.watch(profileProvider);
    final titleStyle = Theme.of(context).textTheme.headlineSmall;

    return Scaffold(
      drawer: const AppDrawer(),
      appBar: AppBar(
        centerTitle: true,
        title: Text('Profile', style: titleStyle),
      ),
      body: profileAsync.when(
        data: (profile) => _ProfileBody(
          profile: profile,
          nameController: _nameController,
          emailController: _emailController,
          phoneController: _phoneController,
          passwordController: _passwordController,
          oldPasswordController: _oldPasswordController,
          newPasswordController: _newPasswordController,
          updating: _updating,
          onUpdateInfo: _updateInfo,
          onUpdatePassword: _updatePassword,
        ),
        loading: () => const LoadingView(),
        error: (error, _) => ErrorView(
          message: _mapError(error),
          onRetry: () => ref.refresh(profileProvider),
        ),
      ),
    );
  }

  String _mapError(Object error) {
    if (error is ApiException) return error.message;
    return 'Failed to load the profile.';
  }
}

class _ProfileBody extends StatefulWidget {
  final User profile;
  final TextEditingController nameController;
  final TextEditingController emailController;
  final TextEditingController phoneController;
  final TextEditingController passwordController;
  final TextEditingController oldPasswordController;
  final TextEditingController newPasswordController;
  final bool updating;
  final VoidCallback onUpdateInfo;
  final VoidCallback onUpdatePassword;

  const _ProfileBody({
    required this.profile,
    required this.nameController,
    required this.emailController,
    required this.phoneController,
    required this.passwordController,
    required this.oldPasswordController,
    required this.newPasswordController,
    required this.updating,
    required this.onUpdateInfo,
    required this.onUpdatePassword,
  });

  @override
  State<_ProfileBody> createState() => _ProfileBodyState();
}

class _ProfileBodyState extends State<_ProfileBody> {
  bool _initialized = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_initialized) {
      widget.nameController.text = widget.profile.nombre;
      widget.emailController.text = widget.profile.email;
      widget.phoneController.text = widget.profile.tlf ?? '';
      _initialized = true;
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        ShadCard(
          title: const Text('Personal Data'),
          footer: ShadButton(
            onPressed: widget.updating ? null : widget.onUpdateInfo,
            child: const Text('Save Changes'),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const SizedBox(height: 16),
              ShadInput(
                controller: widget.nameController,
                placeholder: const Text('Name'),
              ),
              const SizedBox(height: 12),
              ShadInput(
                controller: widget.emailController,
                placeholder: const Text('Email'),
              ),
              const SizedBox(height: 12),
              ShadInput(
                controller: widget.phoneController,
                placeholder: const Text('Phone'),
              ),
              const SizedBox(height: 12),
              ShadInput(
                controller: widget.passwordController,
                placeholder: const Text('Current Password'),
                obscureText: true,
              ),
              const SizedBox(height: 16),
            ],
          ),
        ),
        const SizedBox(height: 24),
        ShadCard(
          title: const Text('Change Password'),
          footer: ShadButton(
            onPressed: widget.updating ? null : widget.onUpdatePassword,
            child: const Text('Update Password'),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const SizedBox(height: 16),
              ShadInput(
                controller: widget.oldPasswordController,
                placeholder: const Text('Current Password'),
                obscureText: true,
              ),
              const SizedBox(height: 12),
              ShadInput(
                controller: widget.newPasswordController,
                placeholder: const Text('New Password'),
                obscureText: true,
              ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ],
    );
  }
}
