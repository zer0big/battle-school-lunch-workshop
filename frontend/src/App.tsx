import { useMemo, useState } from 'react'
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Divider,
  FluentProvider,
  Input,
  Spinner,
  Text,
  Title1,
  Title2,
  Subtitle1,
  Body1,
  Caption1,
  MessageBar,
  MessageBarBody,
  MessageBarTitle,
  makeStyles,
  tokens,
  webLightTheme,
} from '@fluentui/react-components'
import { Search24Regular, Food24Regular, Calendar24Regular, CheckmarkCircle24Regular } from '@fluentui/react-icons'
import './App.css'

type School = {
  atptOfcdcScCode: string
  atptOfcdcScNm: string
  sdSchulCode: string
  schulNm: string
  schulKndScNm?: string | null
  lctnScNm?: string | null
}

type MealDay = {
  date: string
  menus: string[]
}

type MealResponse = {
  schoolName: string
  startDate: string
  endDate: string
  meals: MealDay[]
  hasData: boolean
  message?: string | null
}

const useStyles = makeStyles({
  app: {
    minHeight: '100vh',
    background: `linear-gradient(180deg, ${tokens.colorNeutralBackground1} 0%, ${tokens.colorNeutralBackground3} 100%)`,
    color: tokens.colorNeutralForeground1,
  },
  shell: {
    maxWidth: '1180px',
    margin: '0 auto',
    padding: '32px 20px 48px',
  },
  hero: {
    display: 'grid',
    gap: '16px',
    marginBottom: '24px',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
    gap: '16px',
  },
  card: {
    borderRadius: '20px',
    boxShadow: '0 12px 30px rgba(15, 23, 42, 0.08)',
  },
  section: {
    display: 'grid',
    gap: '14px',
  },
  row: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '12px',
    alignItems: 'center',
  },
  schoolList: {
    display: 'grid',
    gap: '10px',
  },
  schoolButton: {
    width: '100%',
    justifyContent: 'space-between',
    textAlign: 'left',
  },
  mealList: {
    display: 'grid',
    gap: '12px',
  },
  mealDay: {
    display: 'grid',
    gap: '8px',
    padding: '14px',
    backgroundColor: tokens.colorNeutralBackground2,
    borderRadius: '16px',
  },
  footer: {
    marginTop: '24px',
    color: tokens.colorNeutralForeground3,
  },
})

const today = new Date()
const sevenDaysAgo = new Date()
sevenDaysAgo.setDate(today.getDate() - 7)
const formatDate = (date: Date) => date.toISOString().slice(0, 10)

function App() {
  const styles = useStyles()
  const [query, setQuery] = useState('서울')
  const [schools, setSchools] = useState<School[]>([])
  const [selectedSchool, setSelectedSchool] = useState<School | null>(null)
  const [startDate, setStartDate] = useState(formatDate(sevenDaysAgo))
  const [endDate, setEndDate] = useState(formatDate(today))
  const [mealResult, setMealResult] = useState<MealResponse | null>(null)
  const [loadingSchools, setLoadingSchools] = useState(false)
  const [loadingMeals, setLoadingMeals] = useState(false)
  const [status, setStatus] = useState<string>('학교명을 입력하고 검색해 보세요.')
  const [error, setError] = useState<string | null>(null)

  const selectedLabel = useMemo(() => {
    if (!selectedSchool) return '선택된 학교가 없습니다.'
    return `${selectedSchool.schulNm} · ${selectedSchool.lctnScNm ?? selectedSchool.atptOfcdcScNm}`
  }, [selectedSchool])

  const searchSchools = async () => {
    const trimmed = query.trim()
    if (!trimmed) {
      setError('학교명을 입력하세요.')
      return
    }

    setError(null)
    setStatus('학교를 찾는 중입니다.')
    setLoadingSchools(true)
    try {
      const response = await fetch(`/api/schools?query=${encodeURIComponent(trimmed)}`)
      if (!response.ok) {
        throw new Error('학교 검색에 실패했습니다.')
      }
      const data = (await response.json()) as { schools: School[] }
      setSchools(data.schools)
      setSelectedSchool(data.schools[0] ?? null)
      setMealResult(null)
      setStatus(data.schools.length > 0 ? `${data.schools.length}개 학교를 찾았습니다.` : '검색 결과가 없습니다.')
      if (!data.schools.length) {
        setError('검색 결과 없음')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '알 수 없는 오류가 발생했습니다.')
      setStatus('학교 검색에 실패했습니다.')
    } finally {
      setLoadingSchools(false)
    }
  }

  const searchMeals = async () => {
    if (!selectedSchool) {
      setError('먼저 학교를 선택하세요.')
      return
    }

    if (startDate > endDate) {
      setError('시작일이 종료일보다 늦을 수 없습니다.')
      return
    }

    setError(null)
    setLoadingMeals(true)
    setStatus('급식 정보를 조회하는 중입니다.')
    try {
      const response = await fetch('/api/meals', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          atptOfcdcScCode: selectedSchool.atptOfcdcScCode,
          sdSchulCode: selectedSchool.sdSchulCode,
          schoolName: selectedSchool.schulNm,
          startDate,
          endDate,
        }),
      })

      if (!response.ok) {
        const detail = await response.text()
        throw new Error(detail || '급식 조회에 실패했습니다.')
      }

      const data = (await response.json()) as MealResponse
      setMealResult(data)
      setStatus(data.hasData ? '급식 정보를 불러왔습니다.' : data.message ?? '급식 정보가 없습니다.')
    } catch (err) {
      setError(err instanceof Error ? err.message : '알 수 없는 오류가 발생했습니다.')
      setStatus('급식 조회에 실패했습니다.')
    } finally {
      setLoadingMeals(false)
    }
  }

  return (
    <FluentProvider theme={webLightTheme}>
      <div className={styles.app}>
        <main className={styles.shell}>
          <section className={styles.hero}>
            <Badge appearance="filled" color="brand">
              School Lunch
            </Badge>
            <Title1>급식배틀 - 학교 급식 조회 앱</Title1>
            <Body1>
              학교명을 부분 검색하고, 날짜 범위를 선택해 중식 급식을 날짜별로 확인하세요.
            </Body1>
            <MessageBar intent={error ? 'error' : 'informative'}>
              <MessageBarBody>
                <MessageBarTitle>{error ? '오류' : '상태'}</MessageBarTitle>
                {error ?? status}
              </MessageBarBody>
            </MessageBar>
          </section>

          <div className={styles.grid}>
            <Card className={styles.card}>
              <CardHeader
                header={<Subtitle1>1. 학교 검색 및 선택</Subtitle1>}
                description="학교명 일부만 입력해 검색하세요."
                image={<Search24Regular />}
              />
              <div className={styles.section}>
                <Input
                  value={query}
                  onChange={(_, data) => setQuery(data.value)}
                  placeholder="예: 서울, 강남, 세종"
                />
                <Button appearance="primary" onClick={searchSchools} disabled={loadingSchools}>
                  {loadingSchools ? <Spinner size="tiny" /> : '학교 검색'}
                </Button>

                <div className={styles.schoolList}>
                  {schools.length === 0 ? (
                    <Caption1>검색 결과가 이곳에 표시됩니다.</Caption1>
                  ) : (
                    schools.map((school) => (
                      <Button
                        key={`${school.atptOfcdcScCode}-${school.sdSchulCode}`}
                        className={styles.schoolButton}
                        appearance={selectedSchool?.sdSchulCode === school.sdSchulCode ? 'primary' : 'secondary'}
                        onClick={() => setSelectedSchool(school)}
                      >
                        <span>
                          <Text weight="semibold">{school.schulNm}</Text>
                          <br />
                          <Caption1>
                            {school.lctnScNm ?? school.atptOfcdcScNm} · {school.schulKndScNm ?? '학교'}
                          </Caption1>
                        </span>
                        {selectedSchool?.sdSchulCode === school.sdSchulCode ? (
                          <CheckmarkCircle24Regular />
                        ) : null}
                      </Button>
                    ))
                  )}
                </div>
              </div>
            </Card>

            <Card className={styles.card}>
              <CardHeader
                header={<Subtitle1>2. 날짜 범위 선택</Subtitle1>}
                description="시작일과 종료일을 지정하세요."
                image={<Calendar24Regular />}
              />
              <div className={styles.section}>
                <div className={styles.row}>
                  <label>
                    <Caption1>시작일</Caption1>
                    <Input type="date" value={startDate} onChange={(_, data) => setStartDate(data.value)} />
                  </label>
                  <label>
                    <Caption1>종료일</Caption1>
                    <Input type="date" value={endDate} onChange={(_, data) => setEndDate(data.value)} />
                  </label>
                </div>
                <Divider />
                <Text>{selectedLabel}</Text>
                <Button appearance="primary" onClick={searchMeals} disabled={loadingMeals || !selectedSchool}>
                  {loadingMeals ? <Spinner size="tiny" /> : '급식 조회'}
                </Button>
              </div>
            </Card>
          </div>

          <Card className={styles.card} style={{ marginTop: '16px' }}>
            <CardHeader
              header={<Subtitle1>3. 결과 확인</Subtitle1>}
              description="날짜별 중식 급식이 표시됩니다."
              image={<Food24Regular />}
            />
            <div className={styles.section}>
              {!mealResult ? (
                <Caption1>학교를 선택하고 조회를 실행하면 결과가 표시됩니다.</Caption1>
              ) : mealResult.hasData ? (
                <>
                  <Text weight="semibold">
                    {mealResult.schoolName} · {mealResult.startDate} ~ {mealResult.endDate}
                  </Text>
                  <div className={styles.mealList}>
                    {mealResult.meals.map((meal) => (
                      <div className={styles.mealDay} key={meal.date}>
                        <Subtitle1>{meal.date}</Subtitle1>
                        {meal.menus.length > 0 ? (
                          meal.menus.map((menu) => <Body1 key={menu}>• {menu}</Body1>)
                        ) : (
                          <Caption1>메뉴 정보가 없습니다.</Caption1>
                        )}
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <MessageBar intent="warning">
                  <MessageBarBody>
                    <MessageBarTitle>급식 정보 없음</MessageBarTitle>
                    {mealResult.message ?? '선택한 기간에 급식 정보가 없습니다.'}
                  </MessageBarBody>
                </MessageBar>
              )}
            </div>
          </Card>

          <div className={styles.footer}>
            <Text size={200}>Fluent UI · FastAPI · NEIS Open API</Text>
          </div>
        </main>
      </div>
    </FluentProvider>
  )
}

export default App
