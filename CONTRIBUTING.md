# Contributing

Pull requests are welcome.

Use Python 3.10 or later. The library has no runtime dependencies.
Run checks from the repository folder:

```sh
python3 -m unittest discover -s tests -v
python3 -m local_examiner.demo
```

If pytest is installed, you can use `python3 -m pytest -q`.
To build a wheel, install setuptools 77 or later and wheel. Then run:

```sh
python3 -m pip wheel --no-deps --no-build-isolation --no-index .
```

Use new synthetic texts in tests. Mark them synthetic. Keep rule IDs and
output order stable. Rule changes need evidence and updated tests.

Contributions are accepted under the MIT License. See [LICENSE](LICENSE).
