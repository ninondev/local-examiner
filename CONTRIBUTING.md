# Contributing

Pull requests are welcome. The maintainer reads issues.

Use Python 3.10 or later. The library has no runtime dependencies.
Run checks from the repository folder:

```sh
nice -n 10 python3 -m unittest discover -s tests -v
python3 -m local_examiner.demo
```

If pytest is installed, you can use `nice -n 10 python3 -m pytest -q`.
To build a wheel, install setuptools 77 or later and wheel. Then run:

```sh
nice -n 10 python3 -m pip wheel --no-deps --no-build-isolation --no-index .
```

Use new synthetic texts in tests. Mark them synthetic. Keep rule IDs and
output order stable. Rule changes need evidence and updated tests.

Contributions are accepted under the MIT License. See [LICENSE](LICENSE).
