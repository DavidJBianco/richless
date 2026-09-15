class Richless < Formula
  include Language::Python::Virtualenv

  desc "LESSOPEN filter for Markdown rendering and syntax highlighting with less"
  homepage "https://github.com/DavidJBianco/richless"
  url "https://files.pythonhosted.org/packages/a9/96/79fc2cf58dc624ff1fe9f87f2594461f2d125013834acb6945676e885dd0/richless-0.4.0.tar.gz"
  sha256 "f3402d1080bc6fcddf4ac2a013cbae9876b3ec7025644bc1339d9747de6d05b5"
  license "MIT"
  head "https://github.com/DavidJBianco/richless.git", branch: "main"

  depends_on "python@3.13"

  resource "markdown-it-py" do
    url "https://files.pythonhosted.org/packages/5b/f5/4ec618ed16cc4f8fb3b701563655a69816155e79e24a17b651541804721d/markdown_it_py-4.0.0.tar.gz"
    sha256 "cb0a2b4aa34f932c007117b194e945bd74e0ec24133ceb5bac59009cda1cb9f3"
  end

  resource "mdurl" do
    url "https://files.pythonhosted.org/packages/d6/54/cfe61301667036ec958cb99bd3efefba235e65cdeb9c84d24a8293ba1d90/mdurl-0.1.2.tar.gz"
    sha256 "bb413d29f5eea38f31dd4754dd7377d4465116fb207585f97bf925588687c1ba"
  end

  resource "Pygments" do
    url "https://files.pythonhosted.org/packages/b0/77/a5b8c569bf593b0140bde72ea885a803b82086995367bf2037de0159d924/pygments-2.19.2.tar.gz"
    sha256 "636cb2477cec7f8952536970bc533bc43743542f70392ae026374600add5b887"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/fb/d2/8920e102050a0de7bfabeb4c4614a49248cf8d5d7a8d01885fbb24dc767a/rich-14.2.0.tar.gz"
    sha256 "73ff50c7c0c1c77c8243079283f4edb376f0f6442433aecb8ce7e6d0b92d1fe4"
  end

  def install
    virtualenv_install_with_resources

    # Install the shell integration script
    (share/"richless").install buildpath/"richless-init.sh"
  end

  def caveats
    <<~EOS
      richless 0.4 renders progressively and changes shell integration. Existing shells must reload it:
        . "#{HOMEBREW_PREFIX}/share/richless/richless-init.sh"
      New shells using that stable path pick up the update automatically.
      If your startup file names a version-specific Cellar path, replace that line
      with the stable source command above.
      If you copied richless-init.sh elsewhere, replace that copy and re-source it.
      Use `richless --init-path` to locate the packaged integration script.

      Use --md to force Markdown; -m now retains less's native prompt behavior.
      Start with `less +F FILE` for formatted file following. Pressing F after an
      ordinary rendered-file open does not follow subsequent source changes.
      Unresolved live Markdown switches to raw source after five seconds or 1 MiB.
    EOS
  end

  test do
    (testpath/"test.md").write("# Hello\n\nThis is **bold** text.\n")
    output = shell_output("#{bin}/richless #{testpath}/test.md")
    assert_match "Hello", output
    assert_path_exists shell_output("#{bin}/richless --init-path").strip

    (testpath/"test.py").write("print('hello')\n")
    output = shell_output("#{bin}/richless #{testpath}/test.py")
    assert_match "hello", output
  end

end
