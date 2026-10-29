from pathlib import Path

import pytest

from backend.ingestion.skills.extractor import load_skill_dictionary, load_skill_dictionary_from


def found(text: str) -> set[str]:
    return set(load_skill_dictionary().extract({"description": text}))


@pytest.mark.parametrize(
    ("text", "skill"),
    [
        ("Strong Python and SQL", "python"),
        ("Strong Python and SQL", "sql"),
        ("Power BI dashboards", "power-bi"),
        ("PowerBI", "power-bi"),
        ("Tableau or Looker", "tableau"),
        ("Experience with R and Python", "r"),
        ("Advanced Excel (VLOOKUP)", "excel"),
        ("Microsoft Excel", "excel"),
        ("scikit-learn, pandas, NumPy", "scikit-learn"),
        ("sklearn models", "scikit-learn"),
        ("Postgres or MySQL", "postgresql"),
        ("Google Cloud Platform", "gcp"),
        ("GCP", "gcp"),
        ("Apache Spark", "spark"),
        ("PySpark jobs", "pyspark"),
        ("Airflow DAGs", "airflow"),
        ("dbt models", "dbt"),
        ("Amazon Web Services", "aws"),
        ("Git and Linux", "git"),
        ("C++ and C#", "cpp"),
        ("C++ and C#", "csharp"),
        ("Node.js services", "javascript"),
        ("CI/CD pipelines", "ci-cd"),
        ("Python.", "python"),
    ],
)
def test_detects_skill(text: str, skill: str) -> None:
    assert skill in found(text)


@pytest.mark.parametrize(
    ("text", "skill"),
    [
        ("R&D department", "r"),
        ("React and Redux", "r"),
        ("Our team values creativity", "r"),
        ("You will excel at communication", "excel"),
        ("Excel in a fast-paced team", "excel"),
        ("excellent communicator", "excel"),
        ("GitHub Actions", "git"),
        ("JavaScript only", "java"),
        ("PySpark only", "spark"),
        ("a spark of creativity", "spark"),
        ("Let's go to market", "go"),
        ("transactional email", "sql"),
    ],
)
def test_avoids_false_positives(text: str, skill: str) -> None:
    assert skill not in found(text)


def test_extract_reports_fields_and_is_deterministic() -> None:
    d = load_skill_dictionary()
    fields = {"title": "Data Analyst (SQL)", "tags": "python ; excel", "description": "SQL daily"}
    first = d.extract(fields)
    assert first == d.extract(fields)
    assert first["sql"] == ["description", "title"]
    assert first["python"] == ["tags"]
    assert list(first) == sorted(first)


def test_dictionary_contains_required_skills() -> None:
    slugs = {s.slug for s in load_skill_dictionary().skills}
    required = {
        "python",
        "sql",
        "postgresql",
        "mysql",
        "pandas",
        "numpy",
        "scikit-learn",
        "excel",
        "power-bi",
        "tableau",
        "spark",
        "pyspark",
        "airflow",
        "dbt",
        "aws",
        "azure",
        "gcp",
        "docker",
        "git",
        "linux",
    }
    assert required <= slugs
    assert load_skill_dictionary().version


def test_dictionary_validation_rejects_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "skills.toml"
    path.write_text(
        'version = "t"\ncategories = ["A"]\n'
        '[[skills]]\nslug = "x"\nname = "X"\ncategory = "A"\naliases = ["x"]\n'
        '[[skills]]\nslug = "x"\nname = "X2"\ncategory = "A"\naliases = ["y"]\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_skill_dictionary_from(path)


def test_dictionary_validation_rejects_unknown_category(tmp_path: Path) -> None:
    path = tmp_path / "skills.toml"
    path.write_text(
        'version = "t"\ncategories = ["A"]\n'
        '[[skills]]\nslug = "x"\nname = "X"\ncategory = "B"\naliases = ["x"]\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown categories"):
        load_skill_dictionary_from(path)
