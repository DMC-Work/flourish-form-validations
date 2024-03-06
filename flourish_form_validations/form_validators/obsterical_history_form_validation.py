from django.apps import apps as django_apps
from django.core.exceptions import ValidationError
from edc_form_validators.form_validator import FormValidator

from .crf_form_validator import FormValidatorMixin


class ObstericalHistoryFormValidator(FormValidatorMixin, FormValidator):
    ultrasound_model = 'flourish_caregiver.ultrasound'
    preg_women_screening_model = 'flourish_caregiver.screeningpregwomen'
    antenatal_enrollment_model = 'flourish_caregiver.antenatalenrollment'
    maternal_delivery_model = 'flourish_caregiver.maternaldelivery'

    @property
    def maternal_ultrasound_cls(self):
        return django_apps.get_model(self.ultrasound_model)

    @property
    def preg_women_screening_cls(self):
        return django_apps.get_model(self.preg_women_screening_model)

    @property
    def antenatal_enrollment_cls(self):
        return django_apps.get_model(self.antenatal_enrollment_model)

    @property
    def maternal_delivery_cls(self):
        return django_apps.get_model(self.maternal_delivery_model)

    def clean(self):
        super().clean()
        self.subject_identifier = self.cleaned_data.get(
            'maternal_visit').subject_identifier
        visit_instance = self.cleaned_data.get('maternal_visit', None)
        onschedule_model_cls = self.visit_onschedule_model_cls(visit_instance)
        onschedule_model_obj = self.get_onschedule_model_obj(
            self.subject_identifier, onschedule_model_cls, visit_instance.schedule_name)
        self.child_subject_identifier = self.get_child_subject_identifier(onschedule_model_obj)

        self.validate_ultrasound(cleaned_data=self.cleaned_data)
        self.validate_prev_pregnancies(cleaned_data=self.cleaned_data)
        self.validate_children_delivery(cleaned_data=self.cleaned_data)
        self.validate_pregs_lt_24weeks()

    @property
    def anc_exists(self):
        try:
            self.antenatal_enrollment_cls.objects.get(
                subject_identifier=self.subject_identifier,
                child_subject_identifier=self.child_subject_identifier)
        except self.antenatal_enrollment_cls.DoesNotExist:
            return False
        else:
            return True

    @property
    def ultrasound_ga_confirmed(self):
        maternal_visit = self.cleaned_data.get('maternal_visit')
        subject_identifier = maternal_visit.subject_identifier

        if not self.anc_exists:
            return 0

        try:
            ultrasound = self.maternal_ultrasound_cls.objects.get(
                maternal_visit__subject_identifier=subject_identifier,
                child_subject_identifier=self.child_subject_identifier)
        except self.maternal_ultrasound_cls.DoesNotExist:
            message = 'Please complete ultrasound form first.'
            raise ValidationError(message)
        else:
            return ultrasound.ga_confirmed

    @property
    def has_delivered(self):
        report_datetime = self.cleaned_data.get('report_datetime', None)
        try:
            self.maternal_delivery_cls.objects.get(
                subject_identifier=self.subject_identifier,
                child_subject_identifier=self.child_subject_identifier,
                report_datetime__lte=report_datetime)
        except self.maternal_delivery_cls.DoesNotExist:
            return not self.anc_exists
        else:
            return self.anc_exists
            
    def validate_pregs_lt_24weeks(self):
        pregs_lt_24wks = self.cleaned_data.get('pregs_lt_24wks', 0)
        if pregs_lt_24wks > 1:
            message = {'pregs_lt_24wks':
                       'The number of pregnancies less than 24 weeks '
                       'cannot be more than 1'}
            self._errors.update(message)
            raise ValidationError(message)

        if (self.ultrasound_ga_confirmed and (
                self.ultrasound_ga_confirmed < 24 and pregs_lt_24wks != 1)):
            message = {'pregs_lt_24wks':
                       'Pregnancies less than 24 weeks should be '
                       'equal to 1.'}
            self._errors.update(message)
            raise ValidationError(message)

    def validate_ultrasound(self, cleaned_data=None):
        if not self.anc_exists:
            return 0

        prev_pregnancies = cleaned_data.get('prev_pregnancies')

        if self.ultrasound_ga_confirmed:
            if prev_pregnancies == 1 and self.ultrasound_ga_confirmed > 24:
    
                fields = ['lost_before_24wks', 'lost_after_24wks',
                          'children_died_aft_5yrs']
    
                for field in fields:
                    if (field in cleaned_data and
                            cleaned_data.get(field) != 0):
                        message = {field: 'You indicated previous pregnancies were '
                                          f'{prev_pregnancies}, {field} should be '
                                          f'zero as the current pregnancy is more '
                                          f'than 24 weeks.'}
                        self._errors.update(message)
                        raise ValidationError(message)
    
            elif prev_pregnancies == 1 and self.ultrasound_ga_confirmed < 24:
                fields = ['pregs_24wks_or_more', 'lost_after_24wks', ]
                for field in fields:
                    if cleaned_data.get(field) != 0:
                        raise ValidationError(
                            {field: 'You indicated previous pregnancies were '
                                    f'{prev_pregnancies}, {field} should be '
                                    f'zero as the current pregnancy is not more '
                                    f'than 24 weeks.'})

    def validate_children_delivery(self, cleaned_data=None):
        if None not in [cleaned_data.get('children_deliv_before_37wks'),
                        cleaned_data.get('children_deliv_aftr_37wks'),
                        cleaned_data.get('lost_before_24wks'),
                        cleaned_data.get('lost_after_24wks')]:

            sum_deliv_37_wks = \
                (cleaned_data.get('children_deliv_before_37wks') +
                 cleaned_data.get('children_deliv_aftr_37wks'))
            sum_lost_24_wks = (cleaned_data.get('lost_before_24wks') +
                               cleaned_data.get('lost_after_24wks'))

            children_died_b4_5yrs = cleaned_data.get('children_died_b4_5yrs', 0)
            children_died_aft_5yrs = cleaned_data.get('children_died_aft_5yrs', 0)
            live_children = cleaned_data.get('live_children', 0)
            pregs_24wks_or_more = cleaned_data.get('pregs_24wks_or_more', 0)
            pregs_lt_24wks = cleaned_data.get('pregs_lt_24wks', 0)

            total_pregs = pregs_24wks_or_more + pregs_lt_24wks

            if (live_children != (sum_deliv_37_wks - (
                children_died_b4_5yrs + children_died_aft_5yrs))):
                raise ValidationError({
                    'live_children' :
                    'The sum of Q8 must be equal to (Q11 + Q12) - (Q9 + Q10)'})

            current_preg = (not self.has_delivered and total_pregs == 1)

            if self.has_delivered:
                if (total_pregs and
                    sum_deliv_37_wks != (total_pregs - sum_lost_24_wks)):
                    raise ValidationError('The sum of Q11 and Q12 must be equal to '
                                          '(Q4 + Q5) - (Q6 + Q7). Please correct.')

            # allowance to compansate 1 child, twins or triplets
            # because a single pregnancy can contain a single child, twins or triplets
            no_of_children_allowance = (sum_deliv_37_wks - (children_died_b4_5yrs +
                                                            children_died_aft_5yrs)) + 3

            if live_children > no_of_children_allowance:
                raise ValidationError({
                    'live_children':
                        'Living children must be equal to pregnancies delivered(Q10 + '
                        'Q11) and children lost. Please correct.'})

    def validate_prev_pregnancies(self, cleaned_data=None):

        pregs_24wks_or_more = cleaned_data.get('pregs_24wks_or_more', 0)
        pregs_lt_24wks = cleaned_data.get('pregs_lt_24wks', 0)
        lost_after_24wks = cleaned_data.get('lost_after_24wks', 0)

        sum_pregs = pregs_24wks_or_more + pregs_lt_24wks

        previous_pregs = cleaned_data.get('prev_pregnancies')

        if previous_pregs > 1 and sum_pregs != previous_pregs:
            raise ValidationError('Total pregnancies should be equal to sum of '
                                  'number of pregnancies less than 24 weeks and '
                                  'number of pregnancies at least 24 weeks i.e. (Q4 + Q5)')

        if (self.ultrasound_ga_confirmed and (
                self.ultrasound_ga_confirmed > 24 and pregs_24wks_or_more < 1)):
            message = {'pregs_24wks_or_more':
                           'Pregnancies more than 24 weeks should be '
                           'more than 1 including the current pregnancy'}
            self._errors.update(message)
            raise ValidationError(message)

        if lost_after_24wks > pregs_24wks_or_more:
            message = {'lost_after_24wks':
                           'Pregnancies lost after 24 weeks cannot be '
                           'more than pregnancies atleast 24 weeks'}
            self._errors.update(message)
            raise ValidationError(message)
