# typed: false
# frozen_string_literal: true

# PHILAB Homebrew Formula
#
# This formula allows users to install PHILAB using Homebrew:
#   brew install --cask philab
#
# For development installation:
#   brew install --cask --HEAD philab
#
# Publishing:
#   1. Create a tap repository: homebrew-philab
#   2. Add this formula to: Casks/philab.rb
#   3. Users install via: brew install --cask e-tech-playtech/philab/philab

cask "philab" do
  version "1.0.0"
  sha256 :no_check  # TODO: Add SHA256 of the DMG file

  # Architecture support
  on_arm do
    sha256 :no_check  # TODO: Add SHA256 for ARM64 DMG
    url "https://github.com/E-TECH-PLAYTECH/PHILAB/releases/download/v#{version}/PHILAB-#{version}-arm64.dmg",
        verified: "github.com/E-TECH-PLAYTECH/PHILAB/"
  end

  on_intel do
    sha256 :no_check  # TODO: Add SHA256 for Intel DMG
    url "https://github.com/E-TECH-PLAYTECH/PHILAB/releases/download/v#{version}/PHILAB-#{version}-x86_64.dmg",
        verified: "github.com/E-TECH-PLAYTECH/PHILAB/"
  end

  name "PHILAB"
  desc "Enterprise-ready multi-agent AI interpretability lab for Microsoft Phi-2"
  homepage "https://github.com/E-TECH-PLAYTECH/PHILAB"

  # macOS version requirements
  depends_on macos: ">= :mojave"

  # Python dependency (optional, for development)
  # depends_on formula: "python@3.11"

  # Installation
  app "PHILAB.app"

  # Create symlink for CLI access
  binary "#{appdir}/PHILAB.app/Contents/MacOS/philab", target: "philab"

  # Post-install setup
  postflight do
    # Create data directories
    data_dir = "#{Dir.home}/.philab"
    FileUtils.mkdir_p(data_dir) unless Dir.exist?(data_dir)

    log_dir = "#{Dir.home}/.philab/logs"
    FileUtils.mkdir_p(log_dir) unless Dir.exist?(log_dir)

    # Set permissions
    FileUtils.chmod(0o755, data_dir)
    FileUtils.chmod(0o755, log_dir)
  end

  # Uninstall cleanup
  uninstall quit:      "com.e-tech-playtech.philab",
            launchctl: "com.e-tech-playtech.philab"

  # Clean up data files (with user confirmation)
  zap trash: [
    "~/Library/Application Support/PHILAB",
    "~/Library/Caches/com.e-tech-playtech.philab",
    "~/Library/Logs/PHILAB",
    "~/Library/Preferences/com.e-tech-playtech.philab.plist",
    "~/.philab",
  ]

  # Caveats - important information for users
  caveats <<~EOS
    PHILAB has been installed successfully!

    Getting Started:
      1. Run the CLI: philab --help
      2. Or open PHILAB.app from Applications

    Configuration:
      - Data directory: ~/.philab
      - Logs: ~/.philab/logs

    For service mode (auto-start on boot):
      sudo brew services start philab

    Documentation:
      https://github.com/E-TECH-PLAYTECH/PHILAB

    Issues:
      https://github.com/E-TECH-PLAYTECH/PHILAB/issues
  EOS
end

# Alternative: Formula for building from source (non-cask)
# This would be in Formula/philab.rb instead of Casks/philab.rb
#
# class Philab < Formula
#   desc "Enterprise-ready multi-agent AI interpretability lab"
#   homepage "https://github.com/E-TECH-PLAYTECH/PHILAB"
#   url "https://github.com/E-TECH-PLAYTECH/PHILAB/archive/v1.0.0.tar.gz"
#   sha256 "TODO: Add SHA256 of source tarball"
#   license "MIT"
#   head "https://github.com/E-TECH-PLAYTECH/PHILAB.git", branch: "main"
#
#   depends_on "python@3.11"
#
#   resource "requirements" do
#     url "https://github.com/E-TECH-PLAYTECH/PHILAB/raw/main/requirements.txt"
#     sha256 "TODO: Add SHA256"
#   end
#
#   def install
#     virtualenv_create(libexec, "python3.11")
#     virtualenv_install_with_resources
#
#     # Install the package
#     system libexec/"bin/pip", "install", "--no-deps", "."
#
#     # Create wrapper script
#     (bin/"philab").write_env_script libexec/"bin/philab",
#       PHILAB_DATA_DIR: var/"philab",
#       PHILAB_LOG_DIR: var/"log/philab"
#
#     # Create data directories
#     (var/"philab").mkpath
#     (var/"log/philab").mkpath
#   end
#
#   service do
#     run [opt_bin/"philab", "--mode", "service"]
#     keep_alive true
#     working_dir var/"philab"
#     log_path var/"log/philab/stdout.log"
#     error_log_path var/"log/philab/stderr.log"
#   end
#
#   test do
#     system "#{bin}/philab", "--version"
#   end
# end
