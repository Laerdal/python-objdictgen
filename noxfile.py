import nox

@nox.session(
    python=["3.12", "3.11", "3.10"]
)
def test(session):
    session.install(".[dev]")
    session.run("pytest")
