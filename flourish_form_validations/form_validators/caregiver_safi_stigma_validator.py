from django.forms import ValidationError
from edc_constants.constants import NO, YES, OTHER
from edc_form_validators import FormValidator

from .crf_form_validator import FormValidatorMixin


class CaregiverSafiStigmaFormValidator(FormValidatorMixin, FormValidator):

    def clean(self):
        super().clean()
        self.validate_period_required()
        self.validate_other()

    def validate_other(self):

        fields = ['other_discr_other',
                  'other_discr_period']

        for field in fields:
            self.required_if('ever_happened',
                             field='other_discr',
                             field_required=field)

    def validate_period_required(self):
        fields = [
            'judged',
            'avoided',
            'discriminated',
            'at_home',
            'at_neigborhood',
            'at_religious',
            'finacial_support',
            'social_support',
            'stressed',
            'saddened',
            'isolated',
            'insulted',
            'home_discr',
            'neighborhood_discr',
            'religious_place_discr',
            'clinic_discr',
            'school_discr',
            'social_effect',
            'emotional_effect',
            'education_effect',
            'pespective_changed'
        ]

        for field in fields:

            self.required_if(
                'ever_happened',
                field=field,
                field_required=f'{field}_period'
            )
