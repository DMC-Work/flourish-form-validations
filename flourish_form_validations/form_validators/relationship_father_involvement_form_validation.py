from django.apps import apps as django_apps
from django.forms import ValidationError
from django.conf import settings
from edc_constants.constants import YES, POS, NEG, NO, NOT_APPLICABLE,\
    DONT_KNOW
from edc_form_validators import FormValidator
from flourish_caregiver.helper_classes import MaternalStatusHelper
from flourish_caregiver.constants import PNTA
from .crf_form_validator import FormValidatorMixin


class RelationshipFatherInvolvementFormValidator(FormValidatorMixin, FormValidator):

    maternal_delivery_model = 'flourish_caregiver.maternaldelivery'
    caregiver_child_consent_model = 'flourish_caregiver.caregiverchildconsent'

    @property
    def maternal_delivery_model_cls(self):
        return django_apps.get_model(self.maternal_delivery_model)

    @property
    def caregiver_child_consent_cls(self):
        return django_apps.get_model(self.caregiver_child_consent_model)

    def clean(self):

        self.validate_required_fields()

        self.required_if(NO,
                         field='partner_present',
                         field_required='why_partner_absent')
        self.validate_against_hiv_status(cleaned_data=self.cleaned_data)
        self.required_if(NO,
                         field='living_with_partner',
                         field_required='why_not_living_with_partner')

        self.required_if(YES,
                         field='partner_present',
                         field_required='is_partner_the_father')

        self.required_if(YES,
                         field='ever_separated',
                         field_required='times_separated')

        self.required_if(YES,
                         field='contact_info',
                         field_required='partner_cell')
        is_partner_the_father = self.cleaned_data.get('is_partner_the_father', None)
        biological_father_alive = self.cleaned_data.get('biological_father_alive', None)

        if is_partner_the_father and biological_father_alive:
            if is_partner_the_father == YES and biological_father_alive != YES:
                raise ValidationError({
                    'biological_father_alive':
                    'Currently living with the father, check question 5 '
                })

        self.validate_father_involvement()

        m2m_fields = ['read_books', 'told_stories', 'sang_songs',
                      'took_child_outside', 'played_with_child',
                      'named_with_child', ]
        condition = self.has_delivered
        for field in m2m_fields:
            self.m2m_applicable_if_true(condition, m2m_field=field)
            self.m2m_single_selection_if(
                *[NOT_APPLICABLE, PNTA, 'no_one'],
                m2m_field=field)
            self.m2m_other_specify(
                *['other'],
                m2m_field=field,
                field_other=f'{field}_other')
            self.m2m_response_na(
                [NO, PNTA, DONT_KNOW],
                field='biological_father_alive',
                na_response='father',
                m2m_field=field)

        super().clean()

    def validate_required_fields(self):
        required_fields = [
            'is_partner_the_father',
            'duration_with_partner',
            'partner_age_in_years',
            'living_with_partner',
            'partners_support',
            'ever_separated',
            'separation_consideration',
            'leave_after_fight',
            'relationship_progression',
            'confide_in_partner',
            'relationship_regret',
            'quarrel_frequency',
            'bothering_partner',
            'kissing_partner',
            'engage_in_interests',
            'happiness_in_relationship',
            'future_relationship',
        ]

        for field in required_fields:
            self.required_if(YES, field='partner_present',
                             field_required=field)

    def validate_father_involvement(self):

        required_fields = [
            'father_child_contact',
            'fathers_financial_support',
        ]

        condition = self.has_delivered
        father_alive = self.cleaned_data.get('biological_father_alive', None)

        for field in required_fields:
            self.required_if_true(
                condition and father_alive == YES,
                field_required=field)

        if not condition and self.cleaned_data.get('child_left_alone') > 0:
            raise ValidationError('Field can not be > 0, child not delivered.')

    def validate_against_hiv_status(self, cleaned_data):
        helper = self.maternal_status_helper
        fields = ['disclosure_to_partner',
                  'discussion_with_partner', 'disclose_status']
        if helper.hiv_status == NEG:
            for field in fields:
                if cleaned_data.get(field) and cleaned_data.get(field) != NOT_APPLICABLE:
                    raise ValidationError({
                        field: 'This field is not applicable'
                    })
        else:
            self.not_applicable_if(NO,
                                   field='partner_present',
                                   field_applicable='disclosure_to_partner')

            self.applicable_if(YES, field='disclosure_to_partner',
                               field_applicable='discussion_with_partner'
                               )

            self.applicable_if(NO, field='disclosure_to_partner',
                               field_applicable='disclose_status',
                               )

    def validate_positive_mother(self):
        # Checker when running tests so it does require addition modules
        if settings.APP_NAME != 'flourish_form_validations':
            maternal_visit = self.cleaned_data.get('maternal_visit')
            helper = MaternalStatusHelper(
                maternal_visit, maternal_visit.subject_identifier)

            self.required_if_true(helper.hiv_status == POS,
                                  field_required='disclosure_to_partner')

            self.required_if(YES, field='disclosure_to_partner',
                             field_required='discussion_with_partner')
            self.required_if(NO, field='disclosure_to_partner',
                             field_required='disclose_status')

    @property
    def maternal_status_helper(self):
        cleaned_data = self.cleaned_data
        visit_obj = cleaned_data.get('maternal_visit')
        if visit_obj:
            return MaternalStatusHelper(visit_obj)

    @property
    def has_delivered(self):
        maternal_visit = self.cleaned_data.get('maternal_visit')
        subject_identifier = maternal_visit.subject_identifier
        onschedule_model = self.onschedule_model(instance=maternal_visit)
        model_cls = self.onschedule_model_cls(onschedule_model)
        try:
            model_obj = model_cls.objects.get(
                subject_identifier=subject_identifier,
                schedule_name=maternal_visit.schedule_name)
        except model_cls.DoesNotExist:
            raise ValidationError('Onschedule does not exist.')
        else:
            child_subject_identifier = model_obj.child_subject_identifier
            if self.is_preg_enrol(child_subject_identifier):
                return self.maternal_delivery_model_cls.objects.filter(
                    subject_identifier=subject_identifier,
                    child_subject_identifier=child_subject_identifier).exists()
            return True

    def is_preg_enrol(self, child_subject_identifier):
        consents = self.caregiver_child_consent_cls.objects.filter(
            subject_identifier=child_subject_identifier)
        try:
            consent = consents.latest('consent_datetime')
        except self.caregiver_child_consent_cls.DoesNotExist:
            raise ValidationError('Caregiver consent on behalf of child does not exist.')
        else:
            return consent.preg_enroll

    def m2m_applicable_if_true(self, field_check, m2m_field=None, ):
        message = None
        qs = self.cleaned_data.get(m2m_field)
        if qs and qs.count() > 0:
            selected = {obj.short_name: obj.name for obj in qs}

            if field_check and NOT_APPLICABLE in selected:
                message = {m2m_field: 'This field is applicable'}
#             elif not field_check and NOT_APPLICABLE not in selected:
#                 message = {m2m_field: 'This field is not applicable'}
        if message:
            self._errors.update(message)
            raise ValidationError(message)
        return False

    def m2m_response_na(self, responses, na_response, field=None, m2m_field=None):
        if self.cleaned_data.get(field) in responses:
            qs = self.cleaned_data.get(m2m_field)
            if qs and qs.count() > 0:
                selected = {obj.short_name: obj.name for obj in qs}

                if na_response in selected:
                    message = {m2m_field:
                               f'Can not select {na_response} as a response.'
                               f' {field} is either {", ".join(responses)}.'}
                    self._errors.update(message)
                    raise ValidationError(message)
