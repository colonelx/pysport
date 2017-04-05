from peewee import *

database_proxy = Proxy()


class BaseModel(Model):
    class Meta:
        database = database_proxy


class Settings(BaseModel):
    name = CharField()
    value = CharField()


class Qualification(BaseModel):
    name = CharField()


class Fee(BaseModel):
    name = CharField()
    amount = DecimalField()


class RelayTeam(BaseModel):
    name = CharField()  # description of team


class RaceStatus(BaseModel):
    """
    value: Applied
    value: Proposed
    value: Sanctioned
    value: Canceled
    value: Rescheduled
    """
    value = CharField()


class Race(BaseModel):
    name = CharField()
    discipline = CharField()  # dictionary of race types
    start_time = DateTimeField()  # full date, including the day e.g. 2017-03-07 11:00:00
    end_time = DateTimeField()
    status = ForeignKeyField(RaceStatus)
    url = CharField(null=True)
    information = CharField(null=True)


class Course(BaseModel):
    name = CharField()
    course_family = CharField(null=True)
    length = DoubleField(null=True)
    climb = DoubleField(null=True)
    number_of_controls = DoubleField(null=True)
    race = ForeignKeyField(Race)  # connection to the race
    controls_text = CharField()  # JSON with legs and controls. If you have 500 courses for relay, it will be faster


class CourseControl(BaseModel):
    course = ForeignKeyField(Course)
    control = CharField()
    map_text = CharField(null=True)
    leg_length = DoubleField(null=True)
    score = DoubleField()
    is_radio = BooleanField()  # specify if the control is used as radio/TV control
    status = CharField()  # enabled / disabled - e.g. was stolen, broken


class ResultStatus(BaseModel):
    """
    value: OK
    value: Finished
    value: MissingPunch
    value: Disqualified
    value: DidNotFinish
    value: Active
    value: Inactive
    value: OverTime
    value: SportingWithdrawal
    value: NotCompeting
    value: Moved
    value: MovedUp
    value: DidNotStart
    value: DidNotEnter
    value: Cancelled
    """
    value = CharField()


class Country(BaseModel):
    name = CharField()
    code2 = CharField(max_length=2)
    code3 = CharField(max_length=3)
    digital_code = CharField()
    code = CharField()


class Contact(BaseModel):
    name = CharField()
    value = CharField()


class Address(BaseModel):
    care_of = CharField()
    street = CharField()
    zip_code = CharField()
    city = CharField()
    state = CharField()
    country = ForeignKeyField(Country)


class Organization(BaseModel):
    name = CharField()
    address = ForeignKeyField(Address, null=True)
    contact = ForeignKeyField(Contact, null=True)
    country = ForeignKeyField(Country, null=True)


class Person(BaseModel):
    name = CharField()
    surname = CharField(null=True)
    sex = CharField(null=True, max_length=1)
    year = SmallIntegerField(null=True)  # sometime we have only year of birth
    birth_date = DateField(null=True)
    team = ForeignKeyField(Organization, null=True)
    nationality = ForeignKeyField(Country, null=True)
    address = ForeignKeyField(Address, null=True)
    contact = ForeignKeyField(Contact, null=True)
    world_code = CharField(null=True)  # WRE ID for orienteering and the same
    national_code = CharField(null=True)
    rank = DecimalField(null=True)  # position/scores in word ranking
    qual = ForeignKeyField(Qualification, null=True)  # qualification, used in Russia only


class Entry(BaseModel):
    entry_date = DateTimeField()
    entry_author = ForeignKeyField(Person, null=True)
    entry_team = ForeignKeyField(Organization, null=True)


class ControlCard(BaseModel):
    name = CharField()
    value = CharField()
    is_rented = BooleanField(null=True)  # either card is own or should be returned
    is_returned = BooleanField(null=True)  # used to control the returning of rented cards


class Group(BaseModel):
    """
    Should have name 'Class' according to IOF spec, but this word is reserved in Python
    """
    name = CharField()  # short name, max 5-6 chars e.g. M17
    long_name = CharField()  # to print in official results e.g. 'Juniors before 17 years"
    course = ForeignKeyField(Course)

    sex = CharField(null=True, max_length=1)  # limitation for entry
    min_age = IntegerField(null=True)
    max_age = IntegerField(null=True)

    fee = ForeignKeyField(Fee, null=True)
    max_time = IntegerField(null=True)  # max time for disqualification
    qual_assign_text = TextField(null=True)  # JSON with rules for Qualification calculation (1:MS, 2-6:KMS etc.)
    start_interval = IntegerField(null=True)
    start_corridor = IntegerField(null=True)  # number of start corridor
    order_in_corridor = IntegerField(null=True)  # order in start corridor for automatic start time/bib calculation


class Participation(BaseModel):
    group = ForeignKeyField(Group)  # changed from course by SK
    person = ForeignKeyField(Person)
    control_card = ForeignKeyField(ControlCard)
    bib_number = IntegerField()
    start_time = DateTimeField(null=True)
    finish_time = DateTimeField(null=True)
    comment = CharField(null=True)  # comment (taken from the entry or entered manually)
    entry = ForeignKeyField(Entry, null=True)  # connection with the Entry object
    relay_team = ForeignKeyField(RelayTeam, null=True)  # connection with relay team.
    relay_leg = IntegerField(null=True)  # relay leg. Possible to calculate it from the bib number
    start_group = IntegerField(null=True)  # used in drawing, to specify red/ping and other start groups
    penalty_time = TimeField(null=True)  # time of penalties (marked route, false start)
    penalty_laps = IntegerField(null=True)  # count of penalty legs (marked route)
    status = ForeignKeyField(ResultStatus)
    split_time = TextField(null=True)  # punches