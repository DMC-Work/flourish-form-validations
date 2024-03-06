import re

from django import forms
from django.apps import apps as django_apps
from django.core.exceptions import ValidationError
from edc_base.utils import age, relativedelta
from edc_constants.constants import FEMALE, MALE, NO, NOT_APPLICABLE, YES
from edc_form_validators import FormValidator

from .consents_form_validator_mixin import ConsentsFormValidatorMixin
from .subject_consent_eligibilty import SubjectConsentEligibility


class SubjectConsentFormValidator(ConsentsFormValidatorMixin,
                                  SubjectConsentEligibility, FormValidator):
    prior_screening_model = 'flourish_caregiver.screeningpriorbhpparticipants'

    subject_consent_model = 'flourish_caregiver.subjectconsent'

    caregiver_locator_model = 'flourish_caregiver.caregiverlocator'

    preg_women_screening_model = 'flourish_caregiver.screeningpregwomen'

    delivery_model = 'flourish_caregiver.maternaldelivery'

    @property
    def bhp_prior_screening_cls(self):
        return django_apps.get_model(self.prior_screening_model)

    @property
    def subject_consent_cls(self):
        return django_apps.get_model(self.subject_consent_model)

    @property
    def caregiver_locator_cls(self):
        return django_apps.get_model(self.caregiver_locator_model)

    @property
    def preg_women_screening_cls(self):
        return django_apps.get_model(self.preg_women_screening_model)

    @property
    def delivery_cls(self):
        return django_apps.get_model(self.delivery_model)

    def clean(self):
        cleaned_data = self.cleaned_data
        self.subject_identifier = cleaned_data.get('subject_identifier')
        self.screening_identifier = cleaned_data.get('screening_identifier')
        super().clean()

        self.clean_gender()
        self.clean_full_name_syntax()
        self.validate_prior_participant_names()
        self.clean_initials_with_full_name()
        self.validate_recruit_source()
        self.validate_recruitment_clinic()
        self.validate_is_literate()
        self.validate_dob(cleaned_data=self.cleaned_data)
        self.validate_identity_number(cleaned_data=self.cleaned_data)
        self.validate_hiv_testing()
        self.validate_child_consent()
        self.validate_reconsent()
        self.validate_age()

    def validate_reconsent(self):
        try:
            consent_obj = self.subject_consent_cls.objects.get(
                subject_identifier=self.cleaned_data.get('subject_identifier'),
                version=self.cleaned_data.get('version'))
        except self.subject_consent_cls.DoesNotExist:
            pass
        else:
            consent_dict = consent_obj.__dict__
            consent_fields = [
                'first_name', 'last_name', 'dob', 'recruit_source',
                'recruit_source_other', 'recruitment_clinic',
                'recruitment_clinic_other', 'is_literate', 'identity',
                'identity_type']
            for field in consent_fields:
                if self.cleaned_data.get(field) != consent_dict[field]:
                    message = {field:
                               f'{field} was previously reported as, '
                               f'{consent_dict[field]}, please correct.'}
                    self._errors.update(message)
                    raise ValidationError(message)

    def clean_full_name_syntax(self):
        cleaned_data = self.cleaned_data
        first_name = cleaned_data.get("first_name")
        last_name = cleaned_data.get("last_name")

        if first_name and not re.match(r'^[A-Z]+$|^([A-Z]+[ ][A-Z]+)$', first_name):
            message = {'first_name': 'Ensure first name is letters (A-Z) in '
                                     'upper case, no special characters, except spaces. '
                                     'Maximum 2 first '
                                     'names allowed.'}
            self._errors.update(message)
            raise ValidationError(message)

        if last_name and not re.match(r'^[A-Z-]+$', last_name):
            message = {'last_name': 'Ensure last name is letters (A-Z) in '
                                    'upper case, no special characters, except hyphens.'}
            self._errors.update(message)
            raise ValidationError(message)

        if first_name and first_name != first_name.upper():
            message = {'first_name': 'First name must be in CAPS.'}
            self._errors.update(message)
            raise ValidationError(message)
        if last_name and last_name != last_name.upper():
            message = {'last_name': 'Last name must be in CAPS.'}
            self._errors.update(message)
            raise ValidationError(message)

    def clean_gender(self):

        if self.preg_women_screening and self.cleaned_data.get('gender') == MALE:
            message = {'gender': 'Participant is indicated to be pregnant, '
                                 'cannot be male.'}
            self._errors.update(message)
            raise ValidationError(message)

    def clean_initials_with_full_name(self):
        cleaned_data = self.cleaned_data
        first_name = cleaned_data.get("first_name")
        last_name = cleaned_data.get("last_name")
        initials = cleaned_data.get("initials")
        try:
            middle_name = None
            is_first_name = False
            new_first_name = None
            if first_name and len(first_name.split(' ')) > 1:
                new_first_name = first_name.split(' ')[0]
                middle_name = first_name.split(' ')[1]

            if middle_name and (middle_name and
                                (initials[:1] != new_first_name[:1] or
                                 initials[1:2] != middle_name[:1])):
                is_first_name = True

            elif not middle_name and initials[:1] != first_name[:1]:
                is_first_name = True

            if is_first_name or initials[-1:] != last_name[:1]:
                raise forms.ValidationError(
                    {'initials': 'Initials do not match full name.'},
                    params={
                        'initials': initials,
                        'first_name': first_name,
                        'last_name': last_name},
                    code='invalid')
        except (IndexError, TypeError):
            raise forms.ValidationError('Initials do not match fullname.')

    def validate_prior_participant_names(self):
        if self.bhp_prior_screening:
            prior_screening = self.bhp_prior_screening
            if (prior_screening.mother_alive == YES and
                    prior_screening.flourish_participation == 'interested'):
                first_name = self.cleaned_data.get('first_name')
                last_name = self.cleaned_data.get('last_name')
                gender = self.cleaned_data.get('gender')
                if self.caregiver_locator:
                    prev_fname = self.caregiver_locator.first_name
                    prev_lname = self.caregiver_locator.last_name
                    if prev_fname and prev_lname:
                        if first_name != prev_fname.upper():
                            message = {'first_name':
                                       'Participant is the biological mother, first '
                                       f'name should match {prev_fname}. '}
                            self._errors.update(message)
                            raise ValidationError(message)
                        if last_name != prev_lname.upper():
                            message = {'last_name':
                                       'Participant is the biological mother, last '
                                       f'name should match {prev_lname}. '}
                            self._errors.update(message)
                            raise ValidationError(message)
                if gender != FEMALE:
                    message = {'gender':
                               'Participant is the biological mother, gender '
                               'should be FEMALE. '}
                    self._errors.update(message)
                    raise ValidationError(message)

    def validate_hiv_testing(self):
        self.applicable_if_true(
            self.preg_women_screening is not None and not self.bhp_prior_screening,
            field_applicable='hiv_testing')

    def validate_identity_number(self, cleaned_data=None):
        identity = cleaned_data.get('identity')
        if identity:
            if not re.match('[0-9]+$', identity):
                message = {'identity': 'Identity number must be digits.'}
                self._errors.update(message)
                raise ValidationError(message)
            if cleaned_data.get('identity') != cleaned_data.get(
                    'confirm_identity'):
                msg = {'identity':
                       '\'Identity\' must match \'confirm identity\'.'}
                self._errors.update(msg)
                raise ValidationError(msg)
            if cleaned_data.get('identity_type') == 'country_id':
                if len(cleaned_data.get('identity')) != 9:
                    msg = {'identity':
                           'Country identity provided should contain 9 values.'
                           ' Please correct.'}
                    self._errors.update(msg)
                    raise ValidationError(msg)
                gender = cleaned_data.get('gender')
                if gender == FEMALE and cleaned_data.get('identity')[4] != '2':
                    msg = {'identity':
                           'Participant gender is Female. Please correct '
                           'identity number.'}
                    self._errors.update(msg)
                    raise ValidationError(msg)
                elif gender == MALE and cleaned_data.get('identity')[4] != '1':
                    msg = {'identity':
                           'Participant is Male. Please correct identity '
                           'number.'}
                    self._errors.update(msg)
                    raise ValidationError(msg)

    def validate_dob(self, cleaned_data=None):
        consent_datetime = cleaned_data.get('consent_datetime')

        if cleaned_data.get('dob') and consent_datetime:
            consent_age = relativedelta(
                consent_datetime.date(), cleaned_data.get('dob')).years
            age_in_years = None

            try:
                consent_obj = self.subject_consent_cls.objects.get(
                    screening_identifier=self.cleaned_data.get(
                        'screening_identifier'),
                    version=self.cleaned_data.get('version'))
            except self.subject_consent_cls.DoesNotExist:
                if consent_age and consent_age < 18:
                    message = {'dob':
                               'Participant is less than 18 years, age derived '
                               f'from the DOB is {consent_age}.'}
                    self._errors.update(message)
                    raise ValidationError(message)
            else:
                age_in_years = relativedelta(
                    consent_datetime.date(), consent_obj.dob).years
                if consent_age and consent_age != age_in_years:
                    message = {'dob':
                               'In previous consent the derived age of the '
                               f'participant is {age_in_years}, but age derived '
                               f'from the DOB is {consent_age}.'}
                    self._errors.update(message)
                    raise ValidationError(message)

    def validate_recruit_source(self):
        self.validate_other_specify(
            field='recruit_source',
            other_specify_field='recruit_source_other',
            required_msg=('You indicated that mother first learnt about the '
                          'study from a source other than those in the list '
                          'provided. Please specify source.'),
        )

    def validate_recruitment_clinic(self):
        clinic = self.cleaned_data.get('recruitment_clinic')
        self.validate_other_specify(
            field='recruitment_clinic',
            other_specify_field='recruitment_clinic_other',
            required_msg=('You MUST specify other facility that mother was '
                          f'recruited from as you already indicated {clinic}')
        )

        if (self.preg_women_screening and not self.bhp_prior_screening
                and self.cleaned_data.get('recruitment_clinic') == 'Prior'):
            message = {'recruitment_clinic':
                       'Participant is pregnant, cannot be from prior BHP Study.'}
            self._errors.update(message)
            raise ValidationError(message)

    def validate_is_literate(self):
        self.required_if(
            NO,
            field='is_literate',
            field_required='witness_name',
            required_msg='Participant is illiterate please provide witness\'s name(s).')

    def validate_child_consent(self):
        cleaned_data = self.cleaned_data
        subject_eligibie = self.subject_eligible(cleaned_data=cleaned_data)
        if not subject_eligibie and cleaned_data.get('child_consent') != NOT_APPLICABLE:
            message = {'child_consent':
                       'Caregiver is not eligible for participation, this field '
                       'is not applicable.'}
            self._errors.update(message)
            raise ValidationError(message)
        elif subject_eligibie and self.bhp_prior_screening:
            if cleaned_data.get('child_consent') == NOT_APPLICABLE:
                message = {'child_consent':
                           'Caregiver is eligible for participation, this '
                           'field is applicable.'}
                self._errors.update(message)
                raise ValidationError(message)

    @property
    def bhp_prior_screening(self):

        try:
            bhp_prior_screening = self.bhp_prior_screening_cls.objects.get(
                screening_identifier=self.screening_identifier)
        except self.bhp_prior_screening_cls.DoesNotExist:
            return None
        else:
            return bhp_prior_screening

    @property
    def caregiver_locator(self):
        if self.caregiver_locator_cls:
            try:
                caregiver_locator = self.caregiver_locator_cls.objects.get(
                    screening_identifier=self.screening_identifier)
            except self.caregiver_locator_cls.DoesNotExist:
                return None
            else:
                return caregiver_locator

    @property
    def preg_women_screening(self):
        try:
            preg_women_screening = self.preg_women_screening_cls.objects.get(
                screening_identifier=self.screening_identifier)
        except self.preg_women_screening_cls.DoesNotExist:
            return None
        else:
            return preg_women_screening

    @property
    def preg_delivery(self):
        if self.subject_identifier:
            try:
                self.delivery_cls.objects.get(
                    subject_identifier=self.subject_identifier)
            except self.delivery_cls.DoesNotExist:
                return False
            else:
                return True
        return False

    def validate_age(self):
        """
        Validates if the person being consented is an adult
        """

        dob = self.cleaned_data.get('dob')
        consent_datetime = self.cleaned_data.get('consent_datetime')

        if dob and consent_datetime:
            age_in_years = age(dob, consent_datetime.date()).years

            if age_in_years < 18:
                raise ValidationError(
                    {'dob': 'The consented individual is below 18'})
