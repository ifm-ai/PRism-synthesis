"""
Hidden tests for Spanish datetime/age recognition fix.

This test module verifies that the Microsoft Recognizers Text library
correctly handles both accented (año/años) and unaccented (ano/anos)
forms in Spanish datetime and age expressions.

Key test scenarios from the fix:
1. DatePeriodExtractor: "los anos 90" should extract decade range (unaccented form)
2. DatePeriodExtractor: "los años 90" should extract decade range (accented form)
3. AgeModel: "Tengo diez anos" should extract age with unit "Año" (unaccented form)
"""

import pytest
from recognizers_suite import Culture, recognize_datetime, recognize_age


class TestSpanishDatePeriodExtractor:
    """Test DatePeriodExtractor for decade expressions with unaccented forms."""

    def test_decade_unaccented_anos_90(self):
        """Test 'los anos 90' extracts as decade date range."""
        text = "escrito en los anos 90"
        results = recognize_datetime(text, Culture.Spanish)

        # Should find at least one result
        assert len(results) > 0, "Should recognize 'los anos 90' as a date expression"

        # Find the daterange result (type_name may be 'datetimeV2.daterange')
        date_range_results = [r for r in results if 'daterange' in r.type_name]
        assert len(date_range_results) > 0, "Should have a daterange result"

        # Check that we found "anos 90"
        found_anos_90 = any("anos 90" in r.text.lower() for r in date_range_results)
        assert found_anos_90, "Should extract 'anos 90' as a decade expression"

    def test_decade_accented_anos_90(self):
        """Test 'los años 90' extracts as decade date range."""
        text = "escrito en los años 90"
        results = recognize_datetime(text, Culture.Spanish)

        date_range_results = [r for r in results if 'daterange' in r.type_name]
        assert len(date_range_results) > 0, "Should have a daterange result"

        found_anos_90 = any("años 90" in r.text for r in date_range_results)
        assert found_anos_90, "Should extract 'años 90' as a decade expression"

    def test_decade_relative_unaccented(self):
        """Test 'ultimos 3 anos' extracts as relative date range."""
        text = "escritos en los ultimos 3 anos"
        results = recognize_datetime(text, Culture.Spanish)

        date_range_results = [r for r in results if 'daterange' in r.type_name]
        assert len(date_range_results) > 0, "Should recognize 'ultimos 3 anos' as date range"

        # Should find "anos" as the unit
        found_anos = any("anos" in r.text.lower() for r in date_range_results)
        assert found_anos, "Should extract 'anos' in relative date expression"

    def test_decade_1970s_extraction(self):
        """Test 'los años 1970' extracts correctly."""
        text = "los años 1970"
        results = recognize_datetime(text, Culture.Spanish)

        date_range_results = [r for r in results if 'daterange' in r.type_name]
        assert len(date_range_results) > 0, "Should recognize 'los años 1970'"

    def test_decade_2000s_extraction(self):
        """Test 'los años 2000' extracts correctly."""
        text = "los años 2000"
        results = recognize_datetime(text, Culture.Spanish)

        date_range_results = [r for r in results if 'daterange' in r.type_name]
        assert len(date_range_results) > 0, "Should recognize 'los años 2000'"

    def test_decade_1940s_extraction(self):
        """Test 'los años 40' extracts correctly."""
        text = "los años 40"
        results = recognize_datetime(text, Culture.Spanish)

        date_range_results = [r for r in results if 'daterange' in r.type_name]
        assert len(date_range_results) > 0, "Should recognize 'los años 40'"


class TestSpanishAgeModel:
    """Test AgeModel for age expressions with unaccented forms."""

    def test_age_diez_anos_unaccented(self):
        """Test 'Tengo diez anos' extracts age with unit Año."""
        text = "Tengo diez anos"
        results = recognize_age(text, Culture.Spanish)

        age_results = [r for r in results if r.type_name == 'age']
        assert len(age_results) > 0, "Should recognize 'diez anos' as age expression"

        result = age_results[0]
        assert result.resolution is not None, "Should have resolution"

        # Check value is 10
        value = result.resolution.get('value', '')
        assert value == '10', f"Age value should be 10, got: {value}"

        # Check unit is Año
        unit = result.resolution.get('unit', '')
        assert unit == 'Año', f"Unit should be 'Año', got: {unit}"

    def test_age_numeric_anos(self):
        """Test '5 anos' extracts as age."""
        text = "El niño tiene 5 anos"
        results = recognize_age(text, Culture.Spanish)

        age_results = [r for r in results if r.type_name == 'age']
        assert len(age_results) > 0, "Should recognize '5 anos' as age"

        result = age_results[0]
        value = result.resolution.get('value', '')
        assert value == '5', f"Age value should be 5, got: {value}"

        unit = result.resolution.get('unit', '')
        assert unit == 'Año', f"Unit should be 'Año', got: {unit}"

    def test_age_accented_anos(self):
        """Test '10 años' with accent still works."""
        text = "Tiene 10 años"
        results = recognize_age(text, Culture.Spanish)

        age_results = [r for r in results if r.type_name == 'age']
        assert len(age_results) > 0, "Should recognize '10 años' as age"

        result = age_results[0]
        value = result.resolution.get('value', '')
        assert value == '10', f"Age value should be 10, got: {value}"

        unit = result.resolution.get('unit', '')
        assert unit == 'Año', f"Unit should be 'Año', got: {unit}"


class TestSpanishYearTypeRecognition:
    """Test year type recognition with both accented and unaccented forms."""

    def test_year_type_anos(self):
        """Test 'anos' recognized in year context."""
        text = "en los anos 80"
        results = recognize_datetime(text, Culture.Spanish)

        # Should find date-related results
        date_range_results = [r for r in results if 'daterange' in r.type_name]
        assert len(date_range_results) > 0, "Should recognize 'anos 80' as date expression"

    def test_year_type_años(self):
        """Test 'años' recognized in year context."""
        text = "en los años 80"
        results = recognize_datetime(text, Culture.Spanish)

        date_range_results = [r for r in results if 'daterange' in r.type_name]
        assert len(date_range_results) > 0, "Should recognize 'años 80' as date expression"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
