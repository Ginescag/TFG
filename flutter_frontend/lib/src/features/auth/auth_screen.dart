import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shadcn_ui/shadcn_ui.dart';

import '../../data/api_exception.dart';
import '../../providers.dart';

class AuthScreen extends ConsumerStatefulWidget {
  const AuthScreen({super.key});

  @override
  ConsumerState<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends ConsumerState<AuthScreen> {
  final _loginEmail = TextEditingController();
  final _loginPassword = TextEditingController();

  final _registerName = TextEditingController();
  final _registerEmail = TextEditingController();
  final _registerPassword = TextEditingController();
  final _registerPhone = TextEditingController();

  String _activeTab = 'login';
  bool _loading = false;

  @override
  void dispose() {
    _loginEmail.dispose();
    _loginPassword.dispose();
    _registerName.dispose();
    _registerEmail.dispose();
    _registerPassword.dispose();
    _registerPhone.dispose();
    super.dispose();
  }

  Future<void> _handleLogin() async {
    setState(() => _loading = true);
    try {
      await ref
          .read(authControllerProvider.notifier)
          .login(
            email: _loginEmail.text.trim(),
            password: _loginPassword.text.trim(),
          );
    } on ApiException catch (e) {
      _showError(e.message);
    } catch (_) {
      _showError('Failed to log in.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _handleRegister() async {
    setState(() => _loading = true);
    try {
      await ref
          .read(authControllerProvider.notifier)
          .registerAndLogin(
            nombre: _registerName.text.trim(),
            email: _registerEmail.text.trim(),
            password: _registerPassword.text.trim(),
            tlf: _registerPhone.text.trim().isEmpty
                ? null
                : _registerPhone.text.trim(),
          );
    } on ApiException catch (e) {
      _showError(e.message);
    } catch (_) {
      _showError('Failed to register the user.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _showError(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final titleStyle = Theme.of(context).textTheme.titleSmall;

    return Scaffold(
      appBar: AppBar(
        centerTitle: true,
        title: Image.asset('assets/warden_logo.png', height: 40),
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: ShadTabs<String>(
          value: _activeTab,
          onChanged: (value) => setState(() => _activeTab = value),
          tabBarAlignment: Alignment.center,
          tabBarConstraints: const BoxConstraints(maxWidth: 420),
          tabs: [
            ShadTab(
              value: 'login',
              content: _LoginForm(
                emailController: _loginEmail,
                passwordController: _loginPassword,
                loading: _loading,
                onSubmit: _handleLogin,
              ),
              child: Text('Login', style: titleStyle),
            ),
            ShadTab(
              value: 'register',
              content: _RegisterForm(
                nameController: _registerName,
                emailController: _registerEmail,
                passwordController: _registerPassword,
                phoneController: _registerPhone,
                loading: _loading,
                onSubmit: _handleRegister,
              ),
              child: Text('Register', style: titleStyle),
            ),
          ],
        ),
      ),
    );
  }
}

class _LoginForm extends StatelessWidget {
  final TextEditingController emailController;
  final TextEditingController passwordController;
  final bool loading;
  final VoidCallback onSubmit;

  const _LoginForm({
    required this.emailController,
    required this.passwordController,
    required this.loading,
    required this.onSubmit,
  });

  @override
  Widget build(BuildContext context) {
    return ShadCard(
      title: const Text('Access'),
      description: const Text('Enter your credentials to continue.'),
      footer: ShadButton(
        onPressed: loading ? null : onSubmit,
        child: Text(loading ? 'Logging in...' : 'Login'),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const SizedBox(height: 16),
          ShadInput(
            controller: emailController,
            placeholder: const Text('Email'),
          ),
          const SizedBox(height: 12),
          ShadInput(
            controller: passwordController,
            placeholder: const Text('Password'),
            obscureText: true,
          ),
          const SizedBox(height: 20),
        ],
      ),
    );
  }
}

class _RegisterForm extends StatelessWidget {
  final TextEditingController nameController;
  final TextEditingController emailController;
  final TextEditingController passwordController;
  final TextEditingController phoneController;
  final bool loading;
  final VoidCallback onSubmit;

  const _RegisterForm({
    required this.nameController,
    required this.emailController,
    required this.passwordController,
    required this.phoneController,
    required this.loading,
    required this.onSubmit,
  });

  @override
  Widget build(BuildContext context) {
    return ShadCard(
      title: const Text('Create an account'),
      description: const Text('Register as a new user to manage your robots.'),
      footer: ShadButton(
        onPressed: loading ? null : onSubmit,
        child: Text(loading ? 'Registering...' : 'Create Account'),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const SizedBox(height: 16),
          ShadInput(
            controller: nameController,
            placeholder: const Text('Full Name'),
          ),
          const SizedBox(height: 12),
          ShadInput(
            controller: emailController,
            placeholder: const Text('Email'),
          ),
          const SizedBox(height: 12),
          ShadInput(
            controller: passwordController,
            placeholder: const Text('Password'),
            obscureText: true,
          ),
          const SizedBox(height: 12),
          ShadInput(
            controller: phoneController,
            placeholder: const Text('Phone (optional)'),
          ),
          const SizedBox(height: 20),
        ],
      ),
    );
  }
}
