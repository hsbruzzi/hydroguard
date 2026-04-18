import 'package:flutter/material.dart';
import 'screens/home_screen.dart';

void main() {
  runApp(const HydroGuardApp());
}

class HydroGuardApp extends StatelessWidget {
  const HydroGuardApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'HydroGuard Avellaneda',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blueGrey),
        useMaterial3: true,
      ),
      home: const HomeScreen(),
    );
  }
}
