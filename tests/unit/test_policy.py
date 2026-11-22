import pytest

from kaavamaaraysavustaja.core.policy import (
    PolicyError,
    PolicyLibrary,
    describe_choice,
    load_settings,
    parse_overrides,
)


@pytest.fixture(scope="module")
def library():
    return PolicyLibrary.load()


def test_library_has_l01_to_l07_and_l15(library):
    assert list(library.policies) == [f"L-0{n}" for n in range(1, 8)] + ["L-15"]
    for policy in library.policies.values():
        assert policy.default in policy.options
        assert policy.basis


def test_defaults(library):
    choices = {c.id: c for c in library.resolve()}
    assert choices["L-03"].option == "ei_pilkota"
    assert choices["L-06"].option == "alkuperaiset"
    assert all(c.source == "oletus" for c in choices.values())
    assert describe_choice(choices["L-03"]) == "L-03: ei_pilkota (suositeltu oletus)"


def test_user_choice(library):
    choices = {c.id: c for c in library.resolve({"L-03": "kappaleittain"})}
    assert (choices["L-03"].option, choices["L-03"].source) == ("kappaleittain", "kayttaja")
    assert describe_choice(choices["L-03"]) == "L-03: kappaleittain (käyttäjän valinta)"


def test_unknown_policy_and_option(library):
    with pytest.raises(PolicyError, match="Tuntematon linjaus"):
        library.resolve({"L-99": "x"})
    with pytest.raises(PolicyError, match="tuntematon vaihtoehto"):
        library.resolve({"L-03": "puolittain"})


def test_not_implemented_option(library):
    with pytest.raises(PolicyError, match="ei ole vielä käytettävissä"):
        library.resolve({"L-03": "aiheittain"})


def locked_library():
    data = {
        "versio": 2,
        "linjaukset": [
            {
                "tunnus": "L-03",
                "otsikko": "Sanallisen tekstin pilkkominen",
                "vaihtoehdot": [{"arvo": "ei_pilkota"}, {"arvo": "kappaleittain"}],
                "oletus": "ei_pilkota",
                "lukittu": True,
                "paatos": {"perustelu": "VOOKA", "paivamaara": "2027-03-01", "hyvaksyja": "yleiskaavoitus"},
                "versio": 2,
            }
        ],
    }
    return PolicyLibrary.from_dict(data)


def test_locked_cannot_be_overridden():
    library = locked_library()
    with pytest.raises(PolicyError, match="lukittu"):
        library.resolve({"L-03": "kappaleittain"})
    (choice,) = library.resolve({"L-03": "ei_pilkota"})  # same value is fine
    assert choice.source == "lukittu"
    assert choice.decision["hyvaksyja"] == "yleiskaavoitus"
    assert (
        describe_choice(choice) == "L-03: ei_pilkota (Tampereen linjaus, lukittu: yleiskaavoitus, 2027-03-01)"
    )


def test_locked_needs_decision():
    data = {
        "versio": 1,
        "linjaukset": [
            {
                "tunnus": "L-01",
                "otsikko": "x",
                "vaihtoehdot": [{"arvo": "a"}],
                "oletus": "a",
                "lukittu": True,
                "versio": 1,
            }
        ],
    }
    with pytest.raises(PolicyError, match="päätös"):
        PolicyLibrary.from_dict(data)


def test_parse_overrides():
    assert parse_overrides(["l-03=kappaleittain", "L-06 = katja"]) == {
        "L-03": "kappaleittain",
        "L-06": "katja",
    }
    with pytest.raises(PolicyError):
        parse_overrides(["L-03"])


def test_settings_file(tmp_path):
    path = tmp_path / "valinnat.yaml"
    path.write_text("kartta: '1'\nlinjaukset:\n  L-06: katja\n", encoding="utf-8")
    assert load_settings(path) == {"kartta": "1", "linjaukset": {"L-06": "katja"}}
    path.write_text("tuntematon: 1\n", encoding="utf-8")
    with pytest.raises(PolicyError, match="tuntemattomia"):
        load_settings(path)
