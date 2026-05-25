# vstack -- 30-second launch screencast
#
# Render with:  vhs docs/assets/screencast.tape
#
# Outputs:
#   docs/assets/screencast.gif
#   docs/assets/screencast.mp4

Output docs/assets/screencast.gif
Output docs/assets/screencast.mp4

Set Shell "zsh"
Set FontSize 14
Set Width 1280
Set Height 720
Set Padding 22
Set TypingSpeed 28ms
Set PlaybackSpeed 1.0
Set Theme "Catppuccin Mocha"

# Hidden setup
Hide
Type "cd /Users/ilhanvalani/Desktop/vstack && source .venv/bin/activate && clear" Enter
Sleep 600ms
Show

# Beat 1 (~5s): identify
Type "# vstack -- 34 OB-anchored patterns for AI agents" Enter
Sleep 400ms
Type "pip install valanistack    # already installed" Enter
Sleep 500ms
Type 'python -c "import vstack; print(f'"'"'vstack v{vstack.__version__}'"'"')"' Enter
Sleep 1500ms

# Beat 2 (~4s): vstack-doctor
Type "vstack-doctor --skip-network --only-errors" Enter
Sleep 2000ms

# Beat 3 (~20s): vstack-hello -- the actual demo
Type "clear" Enter
Type "vstack-hello --offline --no-banner" Enter
Sleep 18000ms

# Hold final frame so the AAR is the closing image
Sleep 1500ms
