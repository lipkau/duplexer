"""Tests for CLI functionality."""

from click.testing import CliRunner

from duplexer.cli import cli


def test_interleave_command_success(sample_duplex_pdf, tmp_path):
    """Test interleave command with valid input."""
    runner = CliRunner()
    output = tmp_path / "output.pdf"

    result = runner.invoke(cli, ["interleave", str(sample_duplex_pdf), str(output)])

    assert result.exit_code == 0
    assert output.exists()
    assert "Successfully wrote" in result.output


def test_interleave_command_odd_pages_error(odd_page_pdf, tmp_path):
    """Test interleave command with odd pages fails appropriately."""
    runner = CliRunner()
    output = tmp_path / "output.pdf"

    result = runner.invoke(
        cli,
        [
            "interleave",
            str(odd_page_pdf),
            str(output),
            "--no-insert-blank-lastback",
        ],
    )

    assert result.exit_code == 2
    assert "Error:" in result.output


def test_interleave_command_odd_pages_with_blank(odd_page_pdf, tmp_path):
    """Test interleave command with odd pages and blank insertion."""
    runner = CliRunner()
    output = tmp_path / "output.pdf"

    result = runner.invoke(
        cli,
        [
            "interleave",
            str(odd_page_pdf),
            str(output),
            "--insert-blank-lastback",
        ],
    )

    assert result.exit_code == 0
    assert output.exists()


def test_interleave_command_no_reverse(even_no_reverse_pdf, tmp_path):
    """Test interleave command with --no-reverse-backs."""
    runner = CliRunner()
    output = tmp_path / "output.pdf"

    result = runner.invoke(
        cli,
        ["interleave", str(even_no_reverse_pdf), str(output), "--no-reverse-backs"],
    )

    assert result.exit_code == 0
    assert output.exists()


def test_interleave_command_verbose(sample_duplex_pdf, tmp_path):
    """Test interleave command with verbose flag."""
    runner = CliRunner()
    output = tmp_path / "output.pdf"

    result = runner.invoke(cli, ["interleave", str(sample_duplex_pdf), str(output), "-v"])

    assert result.exit_code == 0
    assert output.exists()


def test_interleave_command_nonexistent_input(tmp_path):
    """Test interleave command with nonexistent input file."""
    runner = CliRunner()
    nonexistent = tmp_path / "doesnotexist.pdf"
    output = tmp_path / "output.pdf"

    result = runner.invoke(cli, ["interleave", str(nonexistent), str(output)])

    assert result.exit_code != 0


def test_watch_command_help():
    """Test that watch command shows help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["watch", "--help"])

    assert result.exit_code == 0
    assert "Watch directory" in result.output
